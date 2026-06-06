class UserTracker:
    def __init__(self):
        pass
        
    def parse_interactions(self, interaction_data):
        """
        Parses raw interaction data from frontend.
        Returns a set of viewed product IDs and a frequency dict of categories.
        Raw data format: list of dicts: [{'id': 'prod_1', 'cat': 'Fashion'}, ...]
        """
        if not interaction_data:
            return set(), {}

        viewed_ids = set()
        cat_counts = {}

        for item in interaction_data:
            # Safely handle potential different type inputs
            pid = item.get("id")
            cat = item.get("cat")
            
            if pid is not None:
                # Handle both string and integer IDs
                viewed_ids.add(str(pid))
            
            if cat:
                cat_counts[cat] = cat_counts.get(cat, 0) + 1

        return viewed_ids, cat_counts
