import numpy as np
import random
from .content_based import ContentBasedModel
from .collaborative import CollaborativeModel
from .tracker import UserTracker

class RecommendationEngine:
    def __init__(self, products):
        self.products = products
        self.id_to_product = {p['id']: p for p in products}
        
        self.content_model = ContentBasedModel(products)
        self.collab_model = CollaborativeModel(products)
        self.tracker = UserTracker()

    def get_recommendations(self, interaction_data, top_n=6):
        """
        Returns top_n product dictionaries based on hybrid scoring.
        interaction_data: list of dicts [{'id': 'prod_1', 'cat': 'Fashion'}, ...]
        """
        viewed_ids, cat_counts = self.tracker.parse_interactions(interaction_data)

        # Baseline: If no interactions, return popular items with a bit of randomness.
        if not viewed_ids and not cat_counts:
            scored_products = []
            for p in self.products:
                pop = self.collab_model.get_popularity_score(p['id'])
                # Random noise to shuffle popular items slightly
                noise = random.uniform(0, 0.2)
                scored_products.append((pop + noise, p))
            scored_products.sort(key=lambda x: x[0], reverse=True)
            return [sp[1] for sp in scored_products[:top_n]]

        # User has interacted. Calculate hybrid scores.
        final_scores = []
        
        # 1. Base content similarity array (mean of similarities for all viewed items)
        agg_similarity = np.zeros(len(self.products))
        valid_views = 0
        for pid in viewed_ids:
            sim = self.content_model.get_similar_items(pid)
            if np.sum(sim) > 0:
                agg_similarity += sim
                valid_views += 1
        
        if valid_views > 0:
            agg_similarity /= valid_views

        # Compute max views to normalize category interactions
        total_views = sum(cat_counts.values()) if cat_counts else 1

        for idx, p in enumerate(self.products):
            pid = p['id']
            # Skip items already viewed to discover new ones
            if pid in viewed_ids:
                continue

            # Content Similarity Score (0 to 1)
            content_score = agg_similarity[idx]
            
            # User Interaction Score (0 to 1)
            cat = p.get('category')
            user_interaction_score = (cat_counts.get(cat, 0) / total_views) if total_views > 0 else 0
            
            # Popularity Score (0 to 1)
            popularity_score = self.collab_model.get_popularity_score(pid)

            # Hybrid Score calculation
            final_score = (0.5 * content_score) + (0.3 * user_interaction_score) + (0.2 * popularity_score)
            
            final_scores.append((final_score, p))

        # Sort by final score descending
        final_scores.sort(key=lambda x: x[0], reverse=True)
        
        recommendations = [item[1] for item in final_scores[:top_n]]
        
        # Fallback if we couldn't get enough recommendations
        if len(recommendations) < top_n:
            pool = [p for p in self.products if p['id'] not in viewed_ids]
            rem_needed = top_n - len(recommendations)
            recommendations.extend(pool[:rem_needed])

        return recommendations
