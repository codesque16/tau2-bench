from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field

from tau2.domains.food_delivery_app.utils import FOOD_DELIVERY_APP_DB_PATH
from tau2.environment.db import DB


class Dish(BaseModel):
    """A menu item at a restaurant."""

    dish_id: str = Field(description="Unique identifier for the dish")
    name: str = Field(description="Name of the dish")
    veg: bool = Field(description="Whether the dish is vegetarian")
    spice_level: str = Field(description="Default spice level: mild, medium, spicy")
    price_inr: float = Field(description="Price in Indian Rupees")
    available: bool = Field(description="Whether the dish is currently available")
    tags: List[str] = Field(default_factory=list, description="Tags e.g. no_egg, popular")


class Restaurant(BaseModel):
    """A restaurant on the platform."""

    restaurant_id: str = Field(description="Unique identifier for the restaurant")
    name: str = Field(description="Restaurant name")
    city: str = Field(description="City")
    locality: str = Field(description="Locality or area")
    is_veg_only: bool = Field(description="Whether the restaurant is vegetarian only")
    cuisines: List[str] = Field(default_factory=list, description="Cuisine types")
    average_prep_time_min: int = Field(description="Average preparation time in minutes")
    delivery_radius_km: float = Field(description="Delivery radius in km")
    rating: float = Field(description="Average rating")
    accepting_orders: bool = Field(description="Whether the restaurant is accepting orders")
    menu: Dict[str, Dish] = Field(default_factory=dict, description="Menu: dish_id -> Dish")


class UserAddress(BaseModel):
    """A saved delivery address."""

    address_id: str = Field(description="Unique identifier for the address")
    label: str = Field(description="Label e.g. Home, Office")
    line1: str = Field(description="Address line 1")
    line2: str = Field(default="", description="Address line 2")
    city: str = Field(description="City")
    state: str = Field(description="State")
    pincode: str = Field(description="PIN code")
    landmark: Optional[str] = Field(default=None, description="Landmark")
    instructions: Optional[str] = Field(default=None, description="Delivery instructions")


class PaymentMethodBase(BaseModel):
    """Base for payment methods."""

    payment_method_id: str = Field(description="Unique identifier for the payment method")
    type: str = Field(description="Type: upi, card, wallet, cod")


class UpiPayment(PaymentMethodBase):
    type: Literal["upi"] = "upi"
    upi_id: str = Field(description="UPI ID")
    provider: Optional[str] = Field(default=None, description="e.g. GPay, PhonePe")
    supports_autopay: bool = False


class CardPayment(PaymentMethodBase):
    type: Literal["card"] = "card"
    brand: str = Field(description="Card brand")
    last4: str = Field(description="Last 4 digits")


class WalletPayment(PaymentMethodBase):
    type: Literal["wallet"] = "wallet"
    balance_inr: float = Field(description="Wallet balance in INR")


class CodPayment(PaymentMethodBase):
    type: Literal["cod"] = "cod"
    allowed: bool = True


PaymentMethod = Union[UpiPayment, CardPayment, WalletPayment, CodPayment]


class User(BaseModel):
    """A user (customer) on the platform."""

    user_id: str = Field(description="Unique identifier for the user")
    full_name: str = Field(description="Full name")
    phone: str = Field(description="Indian mobile number e.g. +91-98765-21001")
    email: str = Field(description="Email address")
    membership_tier: Optional[str] = Field(default=None, description="e.g. Gold, Silver, None")
    membership_free_delivery_threshold_inr: Optional[float] = Field(
        default=None, description="Order value above which delivery is free"
    )
    addresses: List[UserAddress] = Field(default_factory=list, description="Saved addresses")
    default_address_id: Optional[str] = Field(default=None, description="Default delivery address id")
    payment_methods: Dict[str, Any] = Field(
        default_factory=dict, description="payment_method_id -> payment method (upi, card, wallet, cod)"
    )
    default_payment_method_id: Optional[str] = Field(default=None, description="Default payment method id")


class OrderItem(BaseModel):
    """An item in an order."""

    dish_id: str = Field(description="Dish id")
    name: str = Field(description="Dish name")
    quantity: int = Field(description="Quantity")
    price_inr: float = Field(description="Unit price in INR")
    customizations: Dict[str, Any] = Field(default_factory=dict, description="Customizations")


class PaymentBreakdown(BaseModel):
    """Breakdown of order payment."""

    item_total_inr: float = 0.0
    delivery_fee_inr: float = 0.0
    platform_fee_inr: float = 0.0
    packing_fee_inr: float = 0.0
    tax_inr: float = 0.0
    discount_inr: float = 0.0


class OrderPayment(BaseModel):
    """Payment info for an order."""

    payment_method_id: str = Field(description="Payment method used")
    payment_status: str = Field(description="e.g. success, pending")
    paid_amount_inr: float = Field(description="Amount paid in INR")
    breakdown: Optional[PaymentBreakdown] = Field(default=None, description="Fee breakdown")


class DeliveryPartner(BaseModel):
    """Delivery partner assigned to the order."""

    partner_id: str = ""
    masked_phone: str = ""
    name: str = ""


class OrderIssue(BaseModel):
    """An issue (delay, missing item, etc.) on an order."""

    issue_id: str = Field(description="Unique identifier for the issue")
    type: str = Field(description="e.g. delay_watch, missing_item")
    description: Optional[str] = Field(default=None)
    eligible_refund_inr: Optional[float] = Field(default=None)
    eligible_for_delay_credit: Optional[bool] = Field(default=None)
    credit_inr: Optional[float] = Field(default=None)
    status: Optional[str] = Field(default=None, description="e.g. open, pending_user_confirmation")


OrderStatus = Literal[
    "pending_acceptance",
    "accepted",
    "preparing",
    "picked_up",
    "out_for_delivery",
    "delivered",
    "cancelled",
    "refund_initiated",
    "refund_completed",
]


class Order(BaseModel):
    """An order on the platform."""

    order_id: str = Field(description="Unique order id e.g. #FD1001")
    user_id: str = Field(description="User id")
    restaurant_id: str = Field(description="Restaurant id")
    address_id: str = Field(description="Delivery address id")
    status: OrderStatus = Field(description="Current status")
    items: List[OrderItem] = Field(default_factory=list, description="Ordered items")
    placed_at_ist: Optional[str] = Field(default=None)
    accepted_at_ist: Optional[str] = Field(default=None)
    prepared_at_ist: Optional[str] = Field(default=None)
    picked_up_at_ist: Optional[str] = Field(default=None)
    delivered_at_ist: Optional[str] = Field(default=None)
    payment: Optional[OrderPayment] = Field(default=None)
    delivery_partner: Optional[DeliveryPartner] = Field(default=None)
    issues: List[OrderIssue] = Field(default_factory=list)


class FoodDeliveryAppDB(DB):
    """Database for the food delivery app domain."""

    restaurants: Dict[str, Restaurant] = Field(
        description="Dictionary of restaurants indexed by restaurant_id"
    )
    users: Dict[str, User] = Field(
        description="Dictionary of users indexed by user_id"
    )
    orders: Dict[str, Order] = Field(
        description="Dictionary of orders indexed by order_id"
    )

    def get_statistics(self) -> dict[str, Any]:
        num_restaurants = len(self.restaurants)
        num_users = len(self.users)
        num_orders = len(self.orders)
        total_dishes = sum(len(r.menu) for r in self.restaurants.values())
        return {
            "num_restaurants": num_restaurants,
            "num_users": num_users,
            "num_orders": num_orders,
            "total_dishes": total_dishes,
        }


def get_db():
    return FoodDeliveryAppDB.load(FOOD_DELIVERY_APP_DB_PATH)


if __name__ == "__main__":
    db = get_db()
    print(db.get_statistics())
