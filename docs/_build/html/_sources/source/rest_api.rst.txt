REST API Documentation
=======================

.. http:post:: /doc_loader/upload-file

   Uploade un fichier, l'extrait et le divise en chunks.

   :param file: Fichier uploadé par l'utilisateur.
   :type file: UploadFile
   :param max_length: Taille maximale d'un chunk, defaults to 1000
   :type max_length: int, optional
   :param theme: Thème du document, defaults to "Thème générique"
   :type theme: str, optional
   :raises HTTPException: Si aucun contenu n'est extrait ou en cas d'erreur de traitement
   :return: Résultat de l'extraction
   :rtype: List[ExtractedDocument]

.. http:post:: /database/add_document

   Ajoute une liste de documents à la base de données.

   :param documents: Liste des documents à ajouter.
   :type documents: List[DocumentCreate]
   :raises ValueError: Erreur lors de l'ajout des documents.
   :return: Liste des documents ajoutés avec leurs IDs.
   :rtype: List[DocumentResponse]

.. http:delete:: /database/delete_document

   Supprime un document de la base de données en fonction de son ID.

   :param document_id: Identifiant unique du document à supprimer.
   :type document_id: int
   :raises HTTPException: Si le document n'existe pas.
   :return: Confirmation de la suppression.
   :rtype: dict

.. http:put:: /database/update_document

   Met à jour un document existant dans la base de données.

   :param payload: Données pour mettre à jour le document.
   :type payload: DocumentUpdate
   :raises HTTPException: Erreur lors de la mise à jour du document.
   :return: Document mis à jour.
   :rtype: DocumentResponse

.. http:get:: /database/list_documents

   Affiche la liste des documents dans la base de données.

   :return: Liste des documents dans la base de données.
   :rtype: List[DocumentResponse]

.. http:post:: /search/hybrid_search

   Recherche des documents en fonction de la similarité vectorielle et reranking d'une requête et de filtres optionnels.

   :param query: Requête de recherche.
   :type query: str
   :param top_k: Nombre de résultats à retourner, defaults to 10
   :type top_k: int, optional
   :param theme: Thème du document (filtre optionnel).
   :type theme: str, optional
   :param document_type: Type de document (filtre optionnel).
   :type document_type: str, optional
   :param start_date: Date de début pour le filtrage.
   :type start_date: date, optional
   :param end_date: Date de fin pour le filtrage.
   :type end_date: date, optional
   :raises HTTPException: Si une erreur survient lors de la recherche.
   :return: Résultats de la recherche.
   :rtype: SearchResults

.. http:post:: /pipeline/process-and-store

   Charge un fichier, extrait les documents et les insère dans la base de données.

   :param file: Fichier uploadé par l'utilisateur.
   :type file: UploadFile
   :param max_length: Taille maximale d'un chunk, defaults to 1000
   :type max_length: int, optional
   :param theme: Thème à appliquer aux documents, defaults to "Thème générique"
   :type theme: str, optional
   :raises HTTPException: Si une erreur survient lors du traitement.
   :return: Liste des documents ajoutés avec leurs IDs.
   :rtype: List[Dict]