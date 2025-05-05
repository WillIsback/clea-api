from .database import get_db, Document, Chunk, IndexConfig
from .schemas import DocumentCreate, DocumentUpdate
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import (
    insert,
)
from sqlalchemy.orm import (
    Session,
)
from .embeddings import EmbeddingGenerator
from utils import get_logger

# --------------------------------------------------------------------------- #
#  Configuration du logger
# --------------------------------------------------------------------------- #
logger = get_logger("vectordb.crud")


##############################################################
#  Fonction helper
##############################################################
def add_document_with_chunks(
    db: Session, doc: DocumentCreate, chunks: List[Dict[str, Any]], batch_size: int = 10
) -> Dict[str, Any]:
    """Ajoute un document et ses chunks à la base de données en générant les embeddings en mode lot.

    Cette fonction insère un document et tous ses chunks associés,
    génère les embeddings par lots pour améliorer les performances,
    et préserve les relations hiérarchiques entre les chunks.

    Args:
        db: Session SQLAlchemy active.
        doc: Données du document à créer.
        chunks: Liste des chunks définis par l'utilisateur.
        batch_size: Nombre de chunks à traiter par lot.

    Returns:
        Dict contenant l'ID du document, le nombre de chunks, le corpus_id et si un index doit être créé.
    """
    # Générer un corpus_id si non fourni
    if not doc.corpus_id:
        doc.corpus_id = str(uuid.uuid4())

    # Vérifier si ce corpus nécessite un index
    index_needed = False
    cfg = db.query(IndexConfig).filter(IndexConfig.corpus_id == doc.corpus_id).first()

    if not cfg:
        # Nouveau corpus sans configuration - index nécessaire
        index_needed = True
    elif not cfg.is_indexed:
        # Corpus existant mais pas encore indexé
        index_needed = True

    # Créer le document avec le drapeau index_needed approprié
    document = Document(**doc.model_dump(), index_needed=index_needed)
    db.add(document)
    db.flush()  # pour obtenir document.id

    # Préparer l'embedding generator
    eg = EmbeddingGenerator()

    # Préparation des structures
    uuid_to_db_id: Dict[Any, int] = {}
    created_chunks: List[Tuple[Chunk, Optional[Any], Optional[Any]]] = []

    try:
        # Traitement par lots
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]

            # Extraire les textes du lot pour générer les embeddings
            batch_texts = [c["content"] for c in batch]
            batch_embeddings = eg.generate_embeddings_batch(batch_texts)

            # Créer les objets Chunk avec leurs embeddings respectifs
            for j, c in enumerate(batch):
                chunk_obj = Chunk(
                    document_id=document.id,
                    content=c["content"],
                    embedding=batch_embeddings[j],
                    start_char=c.get("start_char", 0),
                    end_char=c.get("end_char", len(c["content"])),
                    hierarchy_level=c.get("hierarchy_level", 3),
                )
                db.add(chunk_obj)
                created_chunks.append((chunk_obj, c.get("id"), c.get("parent_id")))

            # Flush après chaque lot pour libérer la mémoire
            db.flush()

        # Construire le mapping local_id -> db_id
        for chunk_obj, local_id, _ in created_chunks:
            if local_id:
                uuid_to_db_id[local_id] = chunk_obj.id

        # Mise à jour des relations parent-enfant
        for chunk_obj, _, parent_id in created_chunks:
            if parent_id:
                parent_db_id = uuid_to_db_id.get(parent_id)
                if parent_db_id:
                    chunk_obj.parent_chunk_id = parent_db_id
        db.flush()

        # Gestion de la configuration d'index
        if not cfg:
            db.add(
                IndexConfig(
                    corpus_id=doc.corpus_id,
                    index_type="ivfflat",
                    chunk_count=len(chunks),
                    is_indexed=False,
                )
            )
        else:
            cfg.chunk_count += len(chunks)
            if cfg.is_indexed:
                # Si le corpus était indexé, il faut maintenant mettre à jour l'index
                cfg.is_indexed = False
                index_needed = True

            if cfg.chunk_count > 300_000 and cfg.index_type == "ivfflat":
                logger.warning(
                    "Corpus %s contient désormais %s chunks, envisager la migration vers un index HNSW",
                    doc.corpus_id,
                    cfg.chunk_count,
                )

        db.commit()
        return {
            "document_id": document.id,
            "chunks": len(chunks),
            "corpus_id": doc.corpus_id,
            "index_needed": index_needed,
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Erreur lors de l'ajout du document et des chunks: {str(e)}")
        raise


def update_document_with_chunks(
    document_update: DocumentUpdate, new_chunks: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """Met à jour un document existant et ses chunks dans la base de données.

    Args:
        document_update: Données de mise à jour du document.
        new_chunks: Nouveaux chunks à ajouter ou à remplacer (si replace_chunks=True).

    Returns:
        Dict[str, Any]: Résultat de l'opération avec les informations mises à jour.
    """
    db = next(get_db())
    try:
        # Trouver le document à mettre à jour
        document = db.query(Document).filter(Document.id == document_update.id).first()
        if not document:
            return {"error": f"Document avec ID {document_update.id} introuvable."}

        # Sauvegarder l'ancien corpus_id pour vérifier s'il change
        old_corpus_id = document.corpus_id

        # Mettre à jour les champs spécifiés du document
        if document_update.title is not None:
            document.title = document_update.title
        if document_update.theme is not None:
            document.theme = document_update.theme
        if document_update.document_type is not None:
            document.document_type = document_update.document_type
        if document_update.publish_date is not None:
            if isinstance(document_update.publish_date, str):
                document.publish_date = datetime.strptime(
                    document_update.publish_date, "%Y-%m-%d"
                )
            else:
                document.publish_date = document_update.publish_date
        if document_update.corpus_id is not None:
            document.corpus_id = document_update.corpus_id

        # Si de nouveaux chunks sont fournis, les ajouter
        chunks_added = 0
        if new_chunks:
            # Préparer l'embedding generator
            eg = EmbeddingGenerator()
            bulk_rows = []

            # Générer des embeddings pour les nouveaux chunks
            for c in new_chunks:
                emb = eg.generate_embedding(c["content"])
                chunk_data = {
                    "document_id": document.id,
                    "content": c["content"],
                    "embedding": emb,
                    "start_char": c.get("start_char", 0),
                    "end_char": c.get("end_char", len(c["content"])),
                    "hierarchy_level": c.get("hierarchy_level", 3),
                    "parent_chunk_id": c.get("parent_chunk_id"),
                }
                bulk_rows.append(chunk_data)

            # Insérer tous les nouveaux chunks en une seule opération
            if bulk_rows:
                db.execute(insert(Chunk), bulk_rows)
                chunks_added = len(bulk_rows)

            # Mettre à jour le nombre de chunks dans la configuration d'index
            if chunks_added > 0:
                cfg = (
                    db.query(IndexConfig)
                    .filter(IndexConfig.corpus_id == document.corpus_id)
                    .first()
                )
                if cfg:
                    cfg.chunk_count += chunks_added

                    # Vérifier si un changement d'index est recommandé
                    if cfg.chunk_count > 300_000 and cfg.index_type == "ivfflat":
                        logger.warning(
                            "Corpus %s contient désormais %s chunks, envisager la migration vers un index HNSW",
                            document.corpus_id,
                            cfg.chunk_count,
                        )
                else:
                    # Créer une nouvelle configuration si elle n'existe pas
                    db.add(
                        IndexConfig(
                            corpus_id=document.corpus_id,
                            index_type="ivfflat",
                            chunk_count=chunks_added,
                        )
                    )

        # Vérifier si le corpus_id a changé, ce qui nécessite une mise à jour des index
        index_needed = False
        if old_corpus_id != document.corpus_id:
            # Mettre à jour les statistiques des deux corpus
            old_cfg = (
                db.query(IndexConfig)
                .filter(IndexConfig.corpus_id == old_corpus_id)
                .first()
            )
            new_cfg = (
                db.query(IndexConfig)
                .filter(IndexConfig.corpus_id == document.corpus_id)
                .first()
            )

            # Compter les chunks du document
            chunk_count = (
                db.query(Chunk).filter(Chunk.document_id == document.id).count()
            )

            if old_cfg:
                old_cfg.chunk_count = max(0, old_cfg.chunk_count - chunk_count)

            if new_cfg:
                new_cfg.chunk_count += chunk_count
            else:
                # Créer une configuration pour le nouveau corpus
                db.add(
                    IndexConfig(
                        corpus_id=document.corpus_id,
                        index_type="ivfflat",
                        chunk_count=chunk_count,
                    )
                )

            index_needed = True

        # Valider les modifications
        db.commit()
        db.refresh(document)

        # Récupérer le nombre total de chunks pour ce document
        total_chunks = db.query(Chunk).filter(Chunk.document_id == document.id).count()

        # Construire le résultat
        result = {
            "id": document.id,
            "title": document.title,
            "theme": document.theme,
            "document_type": document.document_type,
            "publish_date": document.publish_date,
            "corpus_id": document.corpus_id,
            "chunks": {"total": total_chunks, "added": chunks_added},
            "index_needed": index_needed,
        }

        return result

    except Exception as e:
        db.rollback()
        logger.error(
            "Erreur lors de la mise à jour du document %s: %s",
            document_update.id,
            str(e),
        )
        return {"error": str(e)}


def delete_document_chunks(
    document_id: int, chunk_ids: Optional[List[int]] = None
) -> Dict[str, Any]:
    """Supprime des chunks spécifiques d'un document ou tous les chunks si aucun ID n'est spécifié.

    Args:
        document_id: ID du document.
        chunk_ids: Liste des IDs des chunks à supprimer (si None, supprime tous les chunks).

    Returns:
        Dict[str, Any]: Résultat de l'opération.
    """
    db = next(get_db())
    try:
        # Vérifier que le document existe
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            return {"error": f"Document avec ID {document_id} introuvable."}

        # Récupérer la configuration d'index pour ce corpus
        cfg = (
            db.query(IndexConfig)
            .filter(IndexConfig.corpus_id == document.corpus_id)
            .first()
        )

        # Supprimer les chunks spécifiés ou tous les chunks
        if chunk_ids:
            # Vérifier que les chunks appartiennent bien au document
            chunks_to_delete = (
                db.query(Chunk)
                .filter(Chunk.document_id == document_id, Chunk.id.in_(chunk_ids))
                .all()
            )

            if not chunks_to_delete:
                return {"warning": "Aucun chunk correspondant trouvé pour ce document."}

            # Mettre à jour le compteur de chunks dans la configuration d'index
            if cfg:
                cfg.chunk_count -= len(chunks_to_delete)

            # Supprimer les chunks spécifiés
            for chunk in chunks_to_delete:
                db.delete(chunk)

            deleted_count = len(chunks_to_delete)
        else:
            # Compter les chunks pour la mise à jour de la configuration d'index
            chunk_count = (
                db.query(Chunk).filter(Chunk.document_id == document_id).count()
            )

            if cfg:
                cfg.chunk_count -= chunk_count

            # Supprimer tous les chunks du document
            deleted_count = (
                db.query(Chunk).filter(Chunk.document_id == document_id).delete()
            )

        db.commit()

        # Construire le résultat
        result = {
            "document_id": document_id,
            "chunks_deleted": deleted_count,
            "remaining_chunks": db.query(Chunk)
            .filter(Chunk.document_id == document_id)
            .count(),
        }

        return result

    except Exception as e:
        db.rollback()
        logger.error(
            "Erreur lors de la suppression des chunks du document %s: %s",
            document_id,
            str(e),
        )
        return {"error": str(e)}


def delete_document(document_id: int) -> Dict[str, Any]:
    """Supprime un document de la base de données avec tous ses chunks associés.

    Args:
        document_id: ID du document à supprimer.

    Returns:
        Dict[str, Any]: Résultat de l'opération.
    """
    db = next(get_db())
    try:
        # Trouver le document à supprimer
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            return {"error": f"Document avec ID {document_id} introuvable."}

        # Récupérer le corpus_id et mettre à jour la configuration d'index
        corpus_id = document.corpus_id
        if corpus_id:
            # Compter les chunks du document pour mettre à jour les compteurs
            chunk_count = (
                db.query(Chunk).filter(Chunk.document_id == document_id).count()
            )

            # Mettre à jour la configuration d'index
            cfg = (
                db.query(IndexConfig).filter(IndexConfig.corpus_id == corpus_id).first()
            )
            if cfg:
                cfg.chunk_count -= chunk_count

        # Supprimer le document (et ses chunks grâce à la cascade)
        db.delete(document)
        db.commit()

        logger.info("Document avec ID %s supprimé avec succès.", document_id)
        return {"success": f"Document avec ID {document_id} supprimé avec succès."}

    except Exception as e:
        db.rollback()
        logger.error(
            "Erreur lors de la suppression du document %s: %s", document_id, str(e)
        )
        return {"error": str(e)}
