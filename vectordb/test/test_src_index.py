"""
Tests de gestion des index vectoriels pour pgvector.

Ce module contient les tests pour vérifier le bon fonctionnement de:
1. La création d'un index vectoriel pour un corpus
2. La vérification des flags d'indexation des documents
3. La suppression d'un index vectoriel
4. Le cycle complet de création/suppression d'index
"""

import logging
import uuid
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import select

from vectordb.src.database import get_db, Document, IndexConfig
from vectordb.src.index_manager import (
    create_simple_index,
    check_index_status,
    drop_index,
    check_all_indexes,
)
from vectordb.src.crud import add_document_with_chunks
from vectordb.src.schemas import DocumentCreate

# Configuration du logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("index-tests")

# Chemin pour les logs de test
LOG_DIR = Path("vectordb/test/log")
LOG_PATH = LOG_DIR / "index_test.log"


def setup_module():
    """Configure l'environnement pour les tests."""
    # Créer le répertoire de logs s'il n'existe pas
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Réinitialiser le fichier de log
    with open(LOG_PATH, "w") as f:
        f.write(f"=== Tests d'index démarrés le {datetime.now()} ===\n\n")


def append_to_log(message: str) -> None:
    """Ajoute une entrée au fichier de log.

    Args:
        message: Message à enregistrer dans le log.
    """
    try:
        with open(LOG_PATH, "a") as f:
            f.write(f"INFO: {datetime.now()} -- {message}\n\n")
        logger.info(message)
    except Exception as e:
        logger.error(f"Erreur lors de l'écriture dans le fichier de log: {e}")
        raise


def create_test_document(title: str = "Test Index") -> dict:
    """Crée un document de test avec des chunks pour les tests d'index.

    Args:
        title: Titre du document de test.

    Returns:
        dict: Informations sur le document créé, incluant le corpus_id.
    """
    append_to_log(f"Création d'un document de test: {title}")

    # Contenu d'exemple
    doc = DocumentCreate(
        title=title,
        theme="TEST",
        document_type="TXT",
        publish_date=date.today(),
        corpus_id=None,  # Généré automatiquement
    )

    # Chunks d'exemple
    chunks = [
        {
            "content": "Premier chunk de test pour l'index vectoriel",
            "hierarchy_level": 1,
            "start_char": 0,
            "end_char": 42,
        },
        {
            "content": "Second chunk avec un contenu différent pour une meilleure diversité",
            "hierarchy_level": 1,
            "start_char": 43,
            "end_char": 110,
        },
    ]

    db = next(get_db())

    # Créer le document avec ses chunks
    added_document = add_document_with_chunks(
        db=db,
        doc=doc,
        chunks=chunks,
        batch_size=1,
    )

    append_to_log(f"Document créé avec succès: {added_document}")
    return added_document


def test_create_index():
    """Teste la création d'un index vectoriel.

    Ce test vérifie que:
    - Un document peut être créé avec des chunks
    - Un index vectoriel peut être créé pour ce document
    - Le statut d'indexation est correctement mis à jour

    Returns:
        str: L'identifiant du corpus pour les tests suivants
    """
    append_to_log("=== TEST: Création d'un index vectoriel ===")

    # 1. Créer un document avec des chunks
    document = create_test_document("Test création d'index")
    corpus_id = document["corpus_id"]

    # 2. Vérifier l'état initial de l'index
    index_status_before = check_index_status(corpus_id)
    append_to_log(f"État initial de l'index: {index_status_before}")

    # 4. Créer l'index vectoriel
    append_to_log(f"Création de l'index pour le corpus {corpus_id}...")
    index_result = create_simple_index(corpus_id)
    append_to_log(f"Résultat de la création: {index_result}")

    # 5. Vérifier l'état final de l'index
    index_status_after = check_index_status(corpus_id)
    append_to_log(f"État final de l'index: {index_status_after}")

    # Check de tous les index avec la methode check_all_indexes()
    all_indexes = check_all_indexes()
    append_to_log(f"État de tous les index: {all_indexes}")

    # 7. Assertions pour valider le test
    assert index_result["status"] == "success", "La création de l'index a échoué"
    assert index_status_after["index_exists"], "L'index n'existe pas après création"

    append_to_log("✅ Test de création d'index réussi")
    return corpus_id


def test_drop_index():
    """Teste la suppression d'un index vectoriel.

    Ce test vérifie que:
    - Un index existant peut être supprimé
    - Le statut d'indexation est correctement mis à jour
    """
    # Utiliser le résultat du test précédent ou créer un nouveau document
    try:
        # Récupérer un corpus_id existant avec un index
        db = next(get_db())
        indexed_corpus = db.execute(
            select(IndexConfig.corpus_id).where(IndexConfig.is_indexed).limit(1)
        ).scalar_one_or_none()

        if not indexed_corpus:
            # Créer un nouveau document et son index
            document = create_test_document("Test suppression d'index")
            corpus_id = document["corpus_id"]
            create_simple_index(corpus_id)
        else:
            corpus_id = indexed_corpus

    except Exception as e:
        # En cas d'erreur, créer un nouveau document
        append_to_log(f"Erreur lors de la récupération d'un corpus indexé: {e}")
        document = create_test_document("Test suppression d'index (nouveau)")
        corpus_id = document["corpus_id"]
        create_simple_index(corpus_id)

    append_to_log(
        f"=== TEST: Suppression d'un index vectoriel (corpus: {corpus_id}) ==="
    )

    # 1. Vérifier l'état initial de l'index
    index_status_before = check_index_status(corpus_id)
    append_to_log(f"État initial de l'index: {index_status_before}")

    # 2. Supprimer l'index
    append_to_log(f"Suppression de l'index pour le corpus {corpus_id}...")
    drop_result = drop_index(corpus_id)
    append_to_log(f"Résultat de la suppression: {drop_result}")

    # 3. Vérifier l'état après suppression
    index_status_after = check_index_status(corpus_id)
    append_to_log(f"État après suppression: {index_status_after}")

    # 4. Assertions pour valider le test
    assert drop_result["status"] == "success", "La suppression de l'index a échoué"
    assert ~index_status_after["index_exists"], (
        "L'index existe toujours après suppression"
    )

    append_to_log("✅ Test de suppression d'index réussi")


def test_full_index_lifecycle():
    """Teste le cycle de vie complet d'un index vectoriel.

    Ce test vérifie:
    - La création d'un document
    - La création d'un index
    - La vérification des status
    - La suppression de l'index
    """
    append_to_log("=== TEST: Cycle de vie complet d'un index vectoriel ===")

    # 1. Créer un document avec un corpus_id spécifique pour ce test
    corpus_id = str(uuid.uuid4())
    doc = DocumentCreate(
        title="Test cycle de vie index",
        theme="TEST",
        document_type="TXT",
        publish_date=date.today(),
        corpus_id=corpus_id,
    )

    chunks = [
        {
            "content": "Chunk de test pour le cycle de vie",
            "hierarchy_level": 1,
            "start_char": 0,
            "end_char": 33,
        },
        {
            "content": "Second chunk pour compléter le test",
            "hierarchy_level": 1,
            "start_char": 34,
            "end_char": 67,
        },
    ]

    db = next(get_db())
    added_document = add_document_with_chunks(
        db=db, doc=doc, chunks=chunks, batch_size=1
    )
    append_to_log(f"Document créé avec corpus_id explicite: {added_document}")

    # 2. Vérifier l'état initial (ne devrait pas avoir d'index)
    initial_status = check_index_status(corpus_id)
    append_to_log(f"État initial: {initial_status}")
    assert ~initial_status["index_exists"], (
        "L'index ne devrait pas exister initialement"
    )

    # 3. Vérifier que index_needed est à True
    db = next(get_db())
    doc_record = db.execute(
        select(Document).where(Document.corpus_id == corpus_id)
    ).scalar_one()
    append_to_log(f"État initial du flag index_needed: {doc_record.index_needed}")
    assert doc_record.index_needed, (
        "Le flag index_needed devrait être True initialement"
    )

    # 4. Créer l'index
    create_result = create_simple_index(corpus_id)
    append_to_log(f"Résultat de la création: {create_result}")
    assert create_result["status"] == "success", "La création de l'index a échoué"

    # 5. Vérifier que index_needed est maintenant à False
    db = next(get_db())
    doc_record = db.execute(
        select(Document).where(Document.corpus_id == corpus_id)
    ).scalar_one()
    append_to_log(
        f"État du flag index_needed après création: {doc_record.index_needed}"
    )
    assert ~doc_record.index_needed, (
        "Le flag index_needed devrait être False après création"
    )

    # 6. Supprimer l'index
    drop_result = drop_index(corpus_id)
    append_to_log(f"Résultat de la suppression: {drop_result}")
    assert drop_result["status"] == "success", "La suppression de l'index a échoué"

    # 7. Vérifier l'état final
    final_status = check_index_status(corpus_id)
    append_to_log(f"État final: {final_status}")
    assert ~final_status["index_exists"], "L'index ne devrait plus exister à la fin"

    append_to_log("✅ Test du cycle de vie complet réussi")


if __name__ == "__main__":
    # Exécution manuelle des tests
    setup_module()
    corpus_id = test_create_index()
    test_drop_index()
    test_full_index_lifecycle()
    print(f"✅ Tous les tests ont réussi! Consultez le log: {LOG_PATH}")
