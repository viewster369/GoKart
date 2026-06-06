class CollaborativeModel:
    def __init__(self, products):
        self.products = products
        self.popularity_scores = self._compute_popularity()

    def _compute_popularity(self):
        """
        Lightweight simulation of collaborative filtering by computing popularity.
        In a real scenario, this would aggregate views or orders from all users.
        """
        scores = {}
        for p in self.products:
            rating_str = str(p.get('rating', ''))
            try:
                # Extract numeric part (e.g. from "★★★★★ 4.5")
                numeric_rating = float(rating_str.split()[-1])
            except (ValueError, IndexError, AttributeError):
                numeric_rating = 3.0 # Default average if missing

            # Popularity score normalized between 0 to 1
            scores[p['id']] = numeric_rating / 5.0
        return scores

    def get_popularity_score(self, item_id):
        return self.popularity_scores.get(item_id, 0.5)
