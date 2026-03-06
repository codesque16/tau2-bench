#!/usr/bin/env python3
"""
Generate extended food_delivery_app db.json (~80k lines) matching retail scale.
Preserves rest_101, rest_102, rest_103; ananya_singh_1001, rahul_sharma_1002, farhan_khan_1003;
and orders #FD1001-#FD1005 for existing tasks.
"""
import json
import random
from pathlib import Path

# Indian first/last names for users
FIRST_NAMES = [
    "Aarav", "Aditya", "Ananya", "Arjun", "Diya", "Ishita", "Kavya", "Krishna",
    "Meera", "Neha", "Priya", "Rahul", "Riya", "Rohan", "Saanvi", "Siddharth",
    "Vikram", "Anjali", "Farhan", "Karan", "Pooja", "Rajesh", "Sanjay", "Sneha",
    "Vivek", "Yash", "Zara", "Amit", "Deepak", "Kavita", "Manish", "Nisha",
    "Preeti", "Suresh", "Uma", "Varun", "Abhishek", "Bhavya", "Chandan", "Divya",
]
LAST_NAMES = [
    "Sharma", "Singh", "Khan", "Patel", "Reddy", "Kumar", "Nair", "Iyer",
    "Gupta", "Joshi", "Desai", "Mehta", "Shah", "Pillai", "Rao", "Verma",
    "Narayanan", "Kulkarni", "Menon", "Chopra", "Malhotra", "Sethi", "Bose",
    "Banerjee", "Mukherjee", "Das", "Ghosh", "Roy", "Sinha", "Jain", "Agarwal",
]

# Indian cities and states
CITIES = [
    ("Mumbai", "Maharashtra", "4000"),
    ("Delhi", "Delhi", "1100"),
    ("Bengaluru", "Karnataka", "5600"),
    ("Hyderabad", "Telangana", "5000"),
    ("Chennai", "Tamil Nadu", "6000"),
    ("Kolkata", "West Bengal", "7000"),
    ("Pune", "Maharashtra", "4110"),
    ("Ahmedabad", "Gujarat", "3800"),
    ("Jaipur", "Rajasthan", "3020"),
    ("Lucknow", "Uttar Pradesh", "2260"),
    ("Kochi", "Kerala", "6820"),
    ("Nagpur", "Maharashtra", "4400"),
    ("Indore", "Madhya Pradesh", "4520"),
    ("Coimbatore", "Tamil Nadu", "6410"),
    ("Chandigarh", "Chandigarh", "1600"),
]

# Localities per city (sample)
LOCALITIES = [
    "Sector", "Block", "Phase", "Layout", "Road", "Nagar", "Colony", "Enclave",
    "Garden", "Park", "Hills", "Residency", "Apartments", "Central", "East", "West",
]

# Indian dish names by category
DISHES_BY_CUISINE = {
    "North Indian": [
        "Paneer Butter Masala", "Dal Makhani", "Butter Naan", "Tandoori Roti", "Palak Paneer",
        "Chole Bhature", "Rajma Chawal", "Aloo Paratha", "Kadai Chicken", "Mix Veg",
        "Dal Tadka", "Laccha Paratha", "Veg Biryani", "Pav Bhaji", "Seekh Kebab",
        "Pani Puri", "Dahi Puri", "Samosa", "Papdi Chaat", "Aloo Tikki",
    ],
    "South Indian": [
        "Masala Dosa", "Plain Dosa", "Idli", "Uttapam", "Vada", "Filter Coffee",
        "Sambar", "Coconut Chutney", "Medu Vada", "Pongal", "Upma", "Bisi Bele Bath",
        "Mysore Masala Dosa", "Rava Dosa", "Set Dosa", "Pesarattu", "Pongal",
    ],
    "Biryani": [
        "Hyderabadi Chicken Biryani", "Hyderabadi Veg Biryani", "Egg Biryani", "Mutton Biryani",
        "Paneer Biryani", "Veg Biryani", "Kolkata Biryani", "Dum Biryani",
    ],
    "Chinese": [
        "Veg Hakka Noodles", "Chicken Manchurian", "Veg Fried Rice", "Spring Roll",
        "Schezwan Rice", "Honey Chilli Potato", "Dim Sum", "Soup",
    ],
    "Desserts": [
        "Gulab Jamun", "Rasmalai", "Double Ka Meetha", "Kheer", "Gajar Halwa",
        "Jalebi", "Rasgulla", "Kulfi", "Phirni", "Seviyan",
    ],
    "Beverages": [
        "Filter Coffee", "Masala Chai", "Lassi", "Mango Lassi", "Fresh Lime",
        "Buttermilk", "Sharbat", "Jaljeera", "Cold Coffee",
    ],
}

SPICE_LEVELS = ["mild", "medium", "spicy"]
TAGS_POOL = ["popular", "no_egg", "street food", "gravy", "light", "heavy", "beverage", "dessert", "no_onion"]


def load_existing_db():
    p = Path(__file__).parent / "db.json"
    with open(p) as f:
        return json.load(f)


def dish_entry(dish_id: str, name: str, veg: bool, spice: str, price_inr: int, available: bool, tags: list):
    return {
        "dish_id": dish_id,
        "name": name,
        "veg": veg,
        "spice_level": spice,
        "price_inr": price_inr,
        "available": available,
        "tags": tags,
    }


def make_restaurant(rest_id: str, name: str, city: str, locality: str, is_veg: bool, cuisines: list, menu_size: int = 12):
    menu = {}
    dish_num = 1
    for cuisine in cuisines:
        pool = DISHES_BY_CUISINE.get(cuisine, DISHES_BY_CUISINE["North Indian"])
        for _ in range(max(1, menu_size // len(cuisines))):
            name_dish = random.choice(pool)
            dish_id = f"{rest_id.replace('rest_', 'd')}_{rest_id.replace('rest_', '')}{dish_num:02d}"
            menu[dish_id] = dish_entry(
                dish_id, name_dish, is_veg or random.random() > 0.3,
                random.choice(SPICE_LEVELS),
                random.randint(80, 450),
                random.random() > 0.1,
                random.sample(TAGS_POOL, min(3, len(TAGS_POOL))),
            )
            dish_num += 1
    return {
        "restaurant_id": rest_id,
        "name": name,
        "city": city,
        "locality": locality,
        "is_veg_only": is_veg,
        "cuisines": cuisines,
        "average_prep_time_min": random.randint(18, 40),
        "delivery_radius_km": round(random.uniform(4, 8), 1),
        "rating": round(random.uniform(3.8, 4.8), 1),
        "accepting_orders": random.random() > 0.05,
        "menu": menu,
    }


def make_user(user_id: str, full_name: str, phone: str, email: str, city: str, state: str, pincode: str):
    first, last = full_name.split(maxsplit=1) if " " in full_name else (full_name, "")
    addr_id = f"addr_{user_id}"
    tier = random.choice(["Gold", "Silver", "None", "Platinum"])
    return {
        "user_id": user_id,
        "full_name": full_name,
        "phone": phone,
        "email": email,
        "membership_tier": tier,
        "membership_free_delivery_threshold_inr": 249 if tier == "Gold" else (349 if tier == "Silver" else (199 if tier == "Platinum" else None)),
        "addresses": [
            {
                "address_id": addr_id,
                "label": "Home",
                "line1": f"Block {random.randint(1, 20)}, {random.choice(LOCALITIES)} {random.randint(1, 99)}",
                "line2": f"{city}",
                "city": city,
                "state": state,
                "pincode": pincode,
                "landmark": "Near main road",
                "instructions": "Call on arrival",
            }
        ],
        "default_address_id": addr_id,
        "payment_methods": {
            "upi_1": {"payment_method_id": "upi_1", "type": "upi", "upi_id": f"{first.lower()}@paytm", "provider": "Paytm", "supports_autopay": False},
            "wallet_foodie": {"payment_method_id": "wallet_foodie", "type": "wallet", "balance_inr": round(random.uniform(50, 500), 2)},
        },
        "default_payment_method_id": "upi_1",
    }


def make_order(order_id: str, user_id: str, restaurant_id: str, address_id: str, status: str, rest_menus: dict):
    rest = rest_menus[restaurant_id]
    dish_ids = list(rest.keys())
    if not dish_ids:
        dish_ids = ["dummy"]
    num_items = random.randint(1, 4)
    items = []
    for _ in range(num_items):
        did = random.choice(dish_ids)
        d = rest[did]
        items.append({
            "dish_id": did,
            "name": d["name"],
            "quantity": random.randint(1, 2),
            "price_inr": d["price_inr"],
            "customizations": {"spice_level": d["spice_level"]} if random.random() > 0.5 else {},
        })
    item_total = sum(it["price_inr"] * it["quantity"] for it in items)
    delivery_fee = random.randint(0, 40)
    platform_fee = 5
    packing = random.randint(10, 25)
    tax = round((item_total + delivery_fee + platform_fee + packing) * 0.05, 0)
    paid = item_total + delivery_fee + platform_fee + packing + tax
    return {
        "order_id": order_id,
        "user_id": user_id,
        "restaurant_id": restaurant_id,
        "address_id": address_id,
        "status": status,
        "items": items,
        "placed_at_ist": "2026-03-01T12:00:00",
        "accepted_at_ist": "2026-03-01T12:05:00" if status != "pending_acceptance" else None,
        "prepared_at_ist": "2026-03-01T12:25:00" if status in ("preparing", "picked_up", "out_for_delivery", "delivered") else None,
        "picked_up_at_ist": "2026-03-01T12:35:00" if status in ("out_for_delivery", "delivered") else None,
        "delivered_at_ist": "2026-03-01T13:00:00" if status == "delivered" else None,
        "payment": {
            "payment_method_id": "upi_1",
            "payment_status": "success" if status != "pending_acceptance" else "pending",
            "paid_amount_inr": round(paid, 0) if status != "pending_acceptance" else 0,
            "breakdown": {
                "item_total_inr": item_total,
                "delivery_fee_inr": delivery_fee,
                "platform_fee_inr": platform_fee,
                "packing_fee_inr": packing,
                "tax_inr": int(tax),
                "discount_inr": 0,
            },
        },
        "delivery_partner": {"partner_id": "dp_1", "masked_phone": "XXXXX", "name": "Partner"} if status in ("out_for_delivery", "delivered") else None,
        "issues": [],
    }


def main():
    data = load_existing_db()
    restaurants = dict(data["restaurants"])
    users = dict(data["users"])
    orders = dict(data["orders"])

    # Restaurant name/placeholders for 47 more (rest_101, 102, 103 kept)
    rest_templates = [
        ("rest_104", "Taj Chaat House", "Mumbai", "Bandra", False, ["North Indian", "Chaat"]),
        ("rest_105", "Udipi Garden", "Bengaluru", "Koramangala", True, ["South Indian"]),
        ("rest_106", "Biryani Blues", "Hyderabad", "Jubilee Hills", False, ["Biryani"]),
        ("rest_107", "Punjab Grill", "Delhi", "Connaught Place", False, ["North Indian"]),
        ("rest_108", "Saravana Bhavan", "Chennai", "T Nagar", True, ["South Indian"]),
        ("rest_109", "Oh! Calcutta", "Kolkata", "Park Street", False, ["North Indian"]),
        ("rest_110", "Mainland China", "Pune", "Koregaon Park", False, ["Chinese"]),
        ("rest_111", "Grameen Kulfi", "Ahmedabad", "SG Highway", True, ["Desserts", "Beverages"]),
        ("rest_112", "Lassi Wala", "Jaipur", "MI Road", True, ["Beverages", "North Indian"]),
        ("rest_113", "Andhra Spice", "Hyderabad", "Banjara Hills", False, ["Biryani", "North Indian"]),
        ("rest_114", "Dosa Plaza", "Bengaluru", "Indiranagar", True, ["South Indian"]),
        ("rest_115", "Bikaner Sweets", "Delhi", "Chandni Chowk", True, ["Desserts", "North Indian"]),
        ("rest_116", "Kerala Kitchen", "Kochi", "Marine Drive", False, ["South Indian"]),
        ("rest_117", "Gujarat Bhavan", "Ahmedabad", "Satellite", True, ["North Indian"]),
        ("rest_118", "Bengali Rasoi", "Kolkata", "Salt Lake", False, ["North Indian"]),
        ("rest_119", "Coastal Curry", "Chennai", "Adyar", False, ["South Indian"]),
        ("rest_120", "Maharaja Bhog", "Mumbai", "Andheri", True, ["North Indian"]),
        ("rest_121", "Chai Point", "Bengaluru", "HSR", True, ["Beverages"]),
        ("rest_122", "Kolkata Biryani House", "Kolkata", "Howrah", False, ["Biryani"]),
        ("rest_123", "Idli Express", "Chennai", "Velachery", True, ["South Indian"]),
        ("rest_124", "Mughlai Darbar", "Delhi", "Karol Bagh", False, ["North Indian"]),
        ("rest_125", "Parsi Dhaba", "Mumbai", "Fort", False, ["North Indian"]),
        ("rest_126", "Tamil Mess", "Coimbatore", "RS Puram", True, ["South Indian"]),
        ("rest_127", "Rajasthani Thali", "Jaipur", "Vaishali", True, ["North Indian"]),
        ("rest_128", "Lucknowi Biryani", "Lucknow", "Hazratganj", False, ["Biryani"]),
        ("rest_129", "South Park", "Bengaluru", "Whitefield", True, ["South Indian"]),
        ("rest_130", "North Star", "Chandigarh", "Sector 17", False, ["North Indian"]),
        ("rest_131", "Spice Route", "Nagpur", "Sitabuldi", False, ["North Indian", "Chinese"]),
        ("rest_132", "Malabar Kitchen", "Kochi", "Edappally", False, ["South Indian"]),
        ("rest_133", "Delhi Chaat", "Delhi", "Lajpat Nagar", True, ["Chaat"]),
        ("rest_134", "Bombay Cafe", "Mumbai", "Lower Parel", False, ["North Indian", "Beverages"]),
        ("rest_135", "Hyderabadi House", "Hyderabad", "Secunderabad", False, ["Biryani"]),
        ("rest_136", "Mysore Cafe", "Bengaluru", "Malleshwaram", True, ["South Indian"]),
        ("rest_137", "Punjabi Dhaba", "Pune", "Viman Nagar", False, ["North Indian"]),
        ("rest_138", "Sweet Bengal", "Kolkata", "Ballygunge", True, ["Desserts"]),
        ("rest_139", "Veg Nation", "Ahmedabad", "Prahlad Nagar", True, ["North Indian"]),
        ("rest_140", "Curry Leaves", "Chennai", "Nungambakkam", False, ["South Indian"]),
        ("rest_141", "Tandoor Tales", "Delhi", "Saket", False, ["North Indian"]),
        ("rest_142", "Filter Coffee Co", "Bengaluru", "Jayanagar", True, ["Beverages", "South Indian"]),
        ("rest_143", "Chaat Corner", "Mumbai", "Goregaon", True, ["Chaat"]),
        ("rest_144", "Biryani Express", "Hyderabad", "Kukatpally", False, ["Biryani"]),
        ("rest_145", "Dosa Factory", "Coimbatore", "Gandhipuram", True, ["South Indian"]),
        ("rest_146", "Rajdhani", "Mumbai", "Mulund", True, ["North Indian"]),
        ("rest_147", "Kerala Cafe", "Kochi", "Kakkanad", False, ["South Indian"]),
        ("rest_148", "Pav Bhaji House", "Pune", "Kothrud", True, ["Chaat"]),
        ("rest_149", "Royal Biryani", "Lucknow", "Gomti Nagar", False, ["Biryani"]),
        ("rest_150", "Udupi Grand", "Bengaluru", "Basavanagudi", True, ["South Indian"]),
    ]
    random.seed(42)
    for rest_id, name, city, loc, veg, cuisines in rest_templates:
        restaurants[rest_id] = make_restaurant(rest_id, name, city, loc, veg, cuisines, menu_size=12)

    # Users: keep first 3; add 497 with Indian names
    existing_user_ids = set(users.keys())
    for i in range(497):
        uid = f"user_{1004 + i}"
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        city, state, pincode_s = random.choice(CITIES)
        pincode = pincode_s + str(random.randint(10, 99))
        phone = f"+91-9{random.randint(1000, 9999)}-{random.randint(10000, 99999)}"
        email = f"{first.lower()}.{last.lower()}{i}@example.in"
        users[uid] = make_user(uid, f"{first} {last}", phone, email, city, state, pincode)

    # Orders: keep #FD1001-#FD1005; add 995 more
    rest_menus = {rid: r["menu"] for rid, r in restaurants.items()}
    user_addr = {}
    for uid, u in users.items():
        user_addr[uid] = u["addresses"][0]["address_id"]
    order_num = 1006
    statuses = ["delivered", "delivered", "delivered", "out_for_delivery", "preparing", "accepted", "pending_acceptance", "cancelled"]
    for _ in range(1045):
        oid = f"#FD{order_num}"
        uid = random.choice(list(users.keys()))
        rid = random.choice(list(restaurants.keys()))
        if rid not in rest_menus or not rest_menus[rid]:
            continue
        addr = user_addr.get(uid, "addr_1")
        st = random.choice(statuses)
        orders[oid] = make_order(oid, uid, rid, addr, st, rest_menus)
        order_num += 1

    out = {"restaurants": restaurants, "users": users, "orders": orders}
    out_path = Path(__file__).parent / "db.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    lines = sum(1 for _ in open(out_path))
    print(f"Wrote {out_path} with {len(restaurants)} restaurants, {len(users)} users, {len(orders)} orders, {lines} lines")


if __name__ == "__main__":
    main()
