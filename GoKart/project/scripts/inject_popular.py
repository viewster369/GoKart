
import json
import os

def inject_popular_products():
    path = "data/products.json"
    if not os.path.exists(path):
        print(f"Error: {path} not found.")
        return

    with open(path, "r", encoding="utf-8") as f:
        products = json.load(f)

    popular_items = [
        # --- ELECTRONICS ---
        {
            "id": "popular_001",
            "title": "Apple iPhone 15 Pro (128GB, Natural Titanium)",
            "category": "Electronics",
            "subcategory": "Cell Phones & Accessories",
            "brand": "Apple",
            "price": 999.0,
            "rating": 4.9,
            "image": "https://m.media-amazon.com/images/I/81SigAnN7pL._AC_SL1500_.jpg",
            "source": "amazon",
            "description": "iPhone 15 Pro. Forged in titanium and featuring the groundbreaking A17 Pro chip, a customizable Action button, and a more versatile Pro camera system.",
            "tags": ["iphone", "smartphone", "apple", "mobile", "electronics"],
            "cleaned_title": "Apple iPhone 15 Pro (128GB, Natural Titanium)",
            "short_description": "Forged in titanium and featuring the groundbreaking A17 Pro chip and a versatile Pro camera system."
        },
        {
            "id": "popular_002",
            "title": "Samsung Galaxy S24 Ultra, 256GB, Titanium Gray",
            "category": "Electronics",
            "subcategory": "Cell Phones & Accessories",
            "brand": "Samsung",
            "price": 1299.99,
            "rating": 4.8,
            "image": "https://m.media-amazon.com/images/I/71WjsZqi2zL._AC_SL1500_.jpg",
            "source": "amazon",
            "description": "Meet Galaxy S24 Ultra, the ultimate form of Galaxy Ultra with a new titanium exterior and a 6.8\" flat display. It's an absolute marvel of design.",
            "tags": ["samsung", "galaxy", "smartphone", "android", "mobile"],
            "cleaned_title": "Samsung Galaxy S24 Ultra, 256GB",
            "short_description": "The ultimate form of Galaxy Ultra with a new titanium exterior and a 6.8\" flat display."
        },
        {
            "id": "popular_003",
            "title": "Apple 2024 MacBook Air M3 Laptop (13-inch, 8GB RAM, 256GB SSD)",
            "category": "Electronics",
            "subcategory": "Computers & Accessories",
            "brand": "Apple",
            "price": 1099.0,
            "rating": 4.9,
            "image": "https://m.media-amazon.com/images/I/71ItMdpbdvL._AC_SL1500_.jpg",
            "source": "amazon",
            "description": "The M3 chip brings even greater capabilities to the superportable 13-inch MacBook Air. With up to 18 hours of battery life, you can take it anywhere.",
            "tags": ["macbook", "laptop", "apple", "m3", "computer"],
            "cleaned_title": "Apple 2024 MacBook Air M3 Laptop",
            "short_description": "The M3 chip brings even greater capabilities to the superportable 13-inch MacBook Air."
        },
        {
            "id": "popular_004",
            "title": "Sony WH-1000XM5 Wireless Noise Canceling Headphones",
            "category": "Electronics",
            "subcategory": "Headphones",
            "brand": "Sony",
            "price": 398.0,
            "rating": 4.8,
            "image": "https://m.media-amazon.com/images/I/61vjK2qPOBL._AC_SL1500_.jpg",
            "source": "amazon",
            "description": "The WH-1000XM5 headphones rewrite the rules for distraction-free listening. Two processors control 8 microphones for unprecedented noise canceling.",
            "tags": ["sony", "headphones", "wireless", "noise canceling", "earbuds"],
            "cleaned_title": "Sony WH-1000XM5 Wireless Headphones",
            "short_description": "Two processors control 8 microphones for unprecedented noise canceling and distraction-free listening."
        },
        {
            "id": "popular_005",
            "title": "Apple AirPods Pro (2nd Generation) with MagSafe Case (USB-C)",
            "category": "Electronics",
            "subcategory": "Earbuds",
            "brand": "Apple",
            "price": 249.0,
            "rating": 4.8,
            "image": "https://m.media-amazon.com/images/I/61SUj2W5yXL._AC_SL1500_.jpg",
            "source": "amazon",
            "description": "AirPods Pro feature up to 2x more Active Noise Cancellation, plus Adaptive Transparency, and Personalized Spatial Audio with dynamic head tracking.",
            "tags": ["airpods", "earbuds", "apple", "wireless", "audio"],
            "cleaned_title": "Apple AirPods Pro (2nd Generation)",
            "short_description": "AirPods Pro feature up to 2x more Active Noise Cancellation and Personalized Spatial Audio."
        },
        # --- BOOKS ---
        {
            "id": "popular_006",
            "title": "The Amazing Spider-Man Vol. 1: Coming Home",
            "category": "Books",
            "subcategory": "Comics",
            "brand": "Marvel",
            "price": 14.99,
            "rating": 4.9,
            "image": "https://m.media-amazon.com/images/I/91M9p6Nl0NL._AC_SL1500_.jpg",
            "source": "amazon",
            "description": "Collects Amazing Spider-Man (1999) #30-35. J. Michael Straczynski and John Romita Jr. introduce the mysterious Ezekiel.",
            "tags": ["spiderman", "marvel", "comic", "book", "superhero"],
            "cleaned_title": "The Amazing Spider-Man Vol. 1",
            "short_description": "Spider-Man faces a new mystery in this classic collection from Straczynski and Romita Jr."
        },
        {
            "id": "popular_007",
            "title": "Batman: Year One Deluxe Edition",
            "category": "Books",
            "subcategory": "Comics",
            "brand": "DC Comics",
            "price": 12.99,
            "rating": 4.9,
            "image": "https://m.media-amazon.com/images/I/815-56BndJL._AC_SL1500_.jpg",
            "source": "amazon",
            "description": "A New York Times Bestseller! Frank Miller's classic retelling of Batman's first year in Gotham City.",
            "tags": ["batman", "dc", "comic", "book", "graphic novel"],
            "cleaned_title": "Batman: Year One Deluxe Edition",
            "short_description": "Frank Miller's legendary retelling of Bruce Wayne's first year as the Dark Knight."
        },
        {
            "id": "popular_008",
            "title": "One Piece, Vol. 1: Romance Dawn",
            "category": "Books",
            "subcategory": "Manga",
            "brand": "Viz Media",
            "price": 9.99,
            "rating": 4.9,
            "image": "https://m.media-amazon.com/images/I/8125BD7m89L._AC_SL1500_.jpg",
            "source": "amazon",
            "description": "As a child, Monkey D. Luffy was inspired to become a pirate by listening to the tales of the buccaneer \"Red-Haired\" Shanks.",
            "tags": ["one piece", "manga", "anime", "book", "comic"],
            "cleaned_title": "One Piece, Vol. 1: Romance Dawn",
            "short_description": "Join Monkey D. Luffy on his quest to become the King of the Pirates in this epic manga series."
        }
    ]

    # Prepend popular items so they appear first if order is maintained
    # (Though we sort by rating in the DataProcessor anyway)
    products = popular_items + products

    # Clean up misclassifications while we are at it
    # Move food/instruments out of Electronics if they don't belong
    for p in products:
        title_lower = p.get("title", "").lower()
        if p.get("category") == "Electronics":
            if any(x in title_lower for x in ["ham", "coppa", "salami", "chicken"]):
                p["category"] = "Grocery" # New category or mislabeled
            if any(x in title_lower for x in ["tuba", "french horn", "guitar", "drum"]):
                # If it's a "Smart" instrument it might stay, but mostly these are "Musical Instruments"
                p["category"] = "Sports" # Using Sports as an 'Outdoor/Activity' fallback or just let it be

    with open(path, "w", encoding="utf-8") as f:
        json.dump(products, f, indent=2)

    print(f"Successfully injected {len(popular_items)} popular products and cleaned up categories.")

if __name__ == "__main__":
    inject_popular_products()
