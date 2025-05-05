# Intégration JavaScript du moteur de recherche

Cette documentation explique comment intégrer le moteur de recherche hybride de Cléa-API dans une application JavaScript/TypeScript.

## Configuration du client

```javascript
import axios from 'axios';

const API_URL = 'http://localhost:8080'; // Ou votre URL de déploiement

const cleaClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});
```

## Effectuer une recherche simple

```javascript
async function searchDocuments(query, topK = 10) {
  try {
    const response = await cleaClient.post('/search/hybrid_search', {
      query,
      topK,
    });
    return response.data;
  } catch (error) {
    console.error('Erreur lors de la recherche:', error);
    throw error;
  }
}

// Utilisation
searchDocuments('analyse des risques')
  .then(results => {
    console.log(`${results.totalResults} résultats trouvés`);
    results.results.forEach(chunk => {
      console.log(`[${chunk.score.toFixed(2)}] ${chunk.title}: ${chunk.content.slice(0, 100)}...`);
    });
  });
```

## Recherche avancée avec confiance et normalisation

```javascript
async function advancedSearch(query, options = {}) {
  const defaultOptions = {
    topK: 10,
    theme: null,
    documentType: null,
    startDate: null,
    endDate: null,
    corpusId: null,
    hierarchical: false,
    filterByRelevance: true,
    normalizeScores: true,
  };
  
  const searchParams = {
    query,
    ...defaultOptions,
    ...options,
  };
  
  try {
    const response = await cleaClient.post('/search/hybrid_search', searchParams);
    return response.data;
  } catch (error) {
    console.error('Erreur lors de la recherche avancée:', error);
    throw error;
  }
}

// Utilisation avec évaluation de la confiance
advancedSearch('bonnes pratiques développement durable', {
  theme: 'RSE',
  filterByRelevance: true,
  normalizeScores: true,
})
.then(results => {
  // Analyser le niveau de confiance
  const { confidence } = results;
  console.log(`Confiance: ${confidence.level.toFixed(2)} - ${confidence.message}`);
  
  // Afficher les statistiques
  console.log(`Stats: min=${confidence.stats.min.toFixed(2)}, max=${confidence.stats.max.toFixed(2)}`);
  
  // Gérer le cas où la requête est hors domaine
  if (confidence.level < 0.3) {
    console.log('⚠️ La requête semble être hors du domaine de connaissance');
    // Afficher un message à l'utilisateur
  }
  
  // Afficher les résultats s'il y en a
  if (results.results.length > 0) {
    results.results.forEach(chunk => {
      console.log(`[${chunk.score.toFixed(2)}] ${chunk.title}`);
    });
  } else {
    console.log('Aucun résultat pertinent trouvé');
  }
});
```

## Composant React d'exemple

```jsx
import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_URL = 'http://localhost:8080';

function SearchComponent() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [confidence, setConfidence] = useState(null);
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState(null);

  const handleSearch = async () => {
    if (!query.trim()) return;
    
    setIsSearching(true);
    setError(null);
    
    try {
      const response = await axios.post(`${API_URL}/search/hybrid_search`, {
        query: query.trim(),
        topK: 10,
        filterByRelevance: true,
        normalizeScores: true
      });
      
      setResults(response.data.results);
      setConfidence(response.data.confidence);
    } catch (err) {
      setError('Erreur lors de la recherche');
      console.error(err);
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div className="search-container">
      <div className="search-bar">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Rechercher..."
        />
        <button onClick={handleSearch} disabled={isSearching}>
          {isSearching ? 'Recherche...' : 'Rechercher'}
        </button>
      </div>
      
      {confidence && (
        <div className={`confidence-meter confidence-${Math.floor(confidence.level * 10)}`}>
          <div className="confidence-label">
            Pertinence: {(confidence.level * 100).toFixed(0)}%
          </div>
          <div className="confidence-message">{confidence.message}</div>
        </div>
      )}
      
      {error && <div className="error-message">{error}</div>}
      
      <div className="results-list">
        {results.length === 0 && !isSearching && query && (
          <p>Aucun résultat pertinent trouvé.</p>
        )}
        
        {results.map((result) => (
          <div key={result.chunkId} className="result-item">
            <div className="result-header">
              <h3>{result.title}</h3>
              <span className="score">{(result.score * 100).toFixed(0)}% pertinent</span>
            </div>
            <div className="result-content">{result.content}</div>
            <div className="result-meta">
              Thème: {result.theme} | Type: {result.documentType} | 
              Date: {new Date(result.publishDate).toLocaleDateString()}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default SearchComponent;
```

