from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

class ContentBasedModel:
    def __init__(self, products):
        self.products = products
        self.product_ids = [p['id'] for p in products]
        self.id_to_index = {pid: idx for idx, pid in enumerate(self.product_ids)}
        
        # TF-IDF vectorizer
        self.tfidf = TfidfVectorizer(stop_words='english')
        self.similarity_matrix = None
        
        self._build_matrix()

    def _build_matrix(self):
        """
        Builds the TF-IDF and Cosine Similarity matrix from product text features.
        Uses title, category, subcategory, description, and tags for richer matching.
        """
        corpus = []
        for p in self.products:
            title = p.get('title', '') or p.get('name', '')
            cat = p.get('category', '')
            subcat = p.get('subcategory', '')
            desc = p.get('description', '') or p.get('desc', '')
            tags = ' '.join(p.get('tags', []))
            
            # Category given double weight by repeating it
            text = f"{title} {cat} {cat} {subcat} {desc} {tags}"
            corpus.append(text)
        
        tfidf_matrix = self.tfidf.fit_transform(corpus)
        self.similarity_matrix = cosine_similarity(tfidf_matrix, tfidf_matrix)

    def get_similar_items(self, item_id):
        """
        Returns an array of similarities for the given item.
        """
        idx = self.id_to_index.get(item_id)
        if idx is None:
            return np.zeros(len(self.products))
        return self.similarity_matrix[idx]
