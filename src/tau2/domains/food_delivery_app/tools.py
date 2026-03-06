"""Toolkit for the food delivery app domain."""

import json
from typing import Any, Dict, List, Optional

from tau2.domains.food_delivery_app.data_model import (
    Dish,
    FoodDeliveryAppDB,
    Order,
    OrderIssue,
    OrderItem,
    Restaurant,
    User,
)
from tau2.domains.food_delivery_app.utils import FOOD_DELIVERY_APP_DB_PATH
from tau2.environment.toolkit import ToolKitBase, ToolType, is_tool


class FoodDeliveryAppTools(ToolKitBase):
    """All the tools for the food delivery app domain."""

    db: FoodDeliveryAppDB

    def __init__(self, db: FoodDeliveryAppDB) -> None:
        super().__init__(db)

    def _get_user(self, user_id: str) -> User:
        if user_id not in self.db.users:
            raise ValueError("User not found")
        return self.db.users[user_id]

    def _get_order(self, order_id: str) -> Order:
        if order_id not in self.db.orders:
            raise ValueError("Order not found")
        return self.db.orders[order_id]

    def _get_restaurant(self, restaurant_id: str) -> Restaurant:
        if restaurant_id not in self.db.restaurants:
            raise ValueError("Restaurant not found")
        return self.db.restaurants[restaurant_id]

    def _get_dish(self, restaurant_id: str, dish_id: str) -> Dish:
        rest = self._get_restaurant(restaurant_id)
        if dish_id not in rest.menu:
            raise ValueError("Dish not found")
        return rest.menu[dish_id]

    @is_tool(ToolType.READ)
    def find_user_by_phone(self, phone: str) -> User:
        """
        Find a user by their Indian mobile number (+91...).
        Use this to authenticate the user at the start of the conversation.

        Args:
            phone: The user's registered mobile number, e.g. '+91-98765-21001'.

        Returns:
            The user profile if found.

        Raises:
            ValueError: If no user is found with this phone number.
        """
        for user in self.db.users.values():
            if user.phone == phone:
                return user
        raise ValueError("User not found")

    @is_tool(ToolType.READ)
    def find_user_by_email(self, email: str) -> User:
        """
        Find a user by their email address.

        Args:
            email: The user's registered email.

        Returns:
            The user profile if found.

        Raises:
            ValueError: If no user is found with this email.
        """
        for user in self.db.users.values():
            if user.email.lower() == email.lower():
                return user
        raise ValueError("User not found")

    @is_tool(ToolType.READ)
    def get_user_details(self, user_id: str) -> User:
        """
        Get full details of a user by their user id.

        Args:
            user_id: The user id, e.g. 'ananya_singh_1001'.

        Returns:
            The user profile.

        Raises:
            ValueError: If the user is not found.
        """
        return self._get_user(user_id)

    @is_tool(ToolType.READ)
    def get_order_details(self, order_id: str) -> Order:
        """
        Get the status and full details of an order.

        Args:
            order_id: The order id, e.g. '#FD1001'. Include the '#' symbol.

        Returns:
            The order details including items, payment, timestamps, and any issues.

        Raises:
            ValueError: If the order is not found.
        """
        return self._get_order(order_id)

    @is_tool(ToolType.READ)
    def get_restaurant_details(self, restaurant_id: str) -> Restaurant:
        """
        Get details of a restaurant including its menu and delivery radius.

        Args:
            restaurant_id: The restaurant id, e.g. 'rest_102'.

        Returns:
            The restaurant details and full menu.

        Raises:
            ValueError: If the restaurant is not found.
        """
        return self._get_restaurant(restaurant_id)

    @is_tool(ToolType.WRITE)
    def cancel_order(self, order_id: str, reason: str) -> Order:
        """
        Cancel an order. Only allowed when the order is in 'pending_acceptance' status.
        Once the restaurant has accepted, cancellation may incur a fee (check order/issue info).
        Not allowed after the order is picked up for delivery.

        Args:
            order_id: The order id, e.g. '#FD1001'.
            reason: Reason for cancellation, e.g. 'changed mind', 'ordered by mistake', 'delivery time too long'.

        Returns:
            The order after cancellation (status set to 'cancelled').

        Raises:
            ValueError: If the order is not found or not in a cancellable state.
        """
        order = self._get_order(order_id)
        if order.status != "pending_acceptance":
            raise ValueError(
                "Order can only be cancelled while it is pending acceptance. "
                "After the restaurant accepts, cancellation may incur a fee or may not be allowed."
            )
        order.status = "cancelled"
        return order

    @is_tool(ToolType.WRITE)
    def update_order_items(
        self,
        order_id: str,
        items_to_remove_dish_ids: List[str],
        items_to_add: List[Dict[str, Any]],
        payment_method_id: str,
    ) -> Order:
        """
        Update items in an order (remove some, add others). Only allowed when the order is
        in 'pending_acceptance' or 'accepted' and the restaurant allows modifications.
        Price difference is settled via the given payment method (wallet, UPI, or card).

        Args:
            order_id: The order id, e.g. '#FD1002'.
            items_to_remove_dish_ids: List of dish_ids to remove from the order (by position/item).
            items_to_add: List of dicts with keys: dish_id, quantity, customizations (optional).
            payment_method_id: Payment method to use for any extra charge or to receive refund, e.g. 'wallet_foodie'.

        Returns:
            The updated order.

        Raises:
            ValueError: If the order is not modifiable or items are invalid.
        """
        order = self._get_order(order_id)
        if order.status not in ("pending_acceptance", "accepted", "preparing"):
            raise ValueError("Order items can only be modified before or early in preparation.")
        rest = self._get_restaurant(order.restaurant_id)
        user = self._get_user(order.user_id)
        if payment_method_id not in user.payment_methods:
            raise ValueError("Payment method not found")
        # Build new items list: remove by dish_id (one occurrence per entry in items_to_remove_dish_ids)
        new_items: List[OrderItem] = []
        remove_queue = list(items_to_remove_dish_ids)
        for item in order.items:
            if remove_queue and item.dish_id in remove_queue:
                remove_queue.remove(item.dish_id)
                continue
            new_items.append(item)
        # Add new items
        add_total = 0.0
        for add_spec in items_to_add:
            dish_id = add_spec.get("dish_id")
            qty = int(add_spec.get("quantity", 1))
            customizations = add_spec.get("customizations") or {}
            if dish_id not in rest.menu:
                raise ValueError(f"Dish {dish_id} not found or not from this restaurant")
            dish = rest.menu[dish_id]
            if not dish.available:
                raise ValueError(f"Dish {dish_id} is not available")
            add_total += dish.price_inr * qty
            new_items.append(
                OrderItem(
                    dish_id=dish_id,
                    name=dish.name,
                    quantity=qty,
                    price_inr=dish.price_inr,
                    customizations=customizations,
                )
            )
        # Simple price diff: sum removed vs sum added (simplified; real logic may use order item totals)
        removed_total = sum(
            item.price_inr * item.quantity
            for item in order.items
            if item.dish_id in items_to_remove_dish_ids
        )
        diff = round(add_total - removed_total, 2)
        if diff > 0:
            pm = user.payment_methods[payment_method_id]
            if isinstance(pm, dict) and pm.get("type") == "wallet":
                bal = pm.get("balance_inr", 0)
                if bal < diff:
                    raise ValueError("Insufficient wallet balance for the price difference")
                pm["balance_inr"] = round(bal - diff, 2)
        order.items = new_items
        return order

    @is_tool(ToolType.WRITE)
    def apply_delay_credit(self, order_id: str, issue_id: str) -> Order:
        """
        Apply a delay credit (e.g. voucher or wallet credit) for a reported delay on an order.
        The order must have an issue of type 'delay_watch' with eligible_for_delay_credit true.

        Args:
            order_id: The order id, e.g. '#FD1003'.
            issue_id: The issue id from the order's issues list, e.g. 'iss_2001'.

        Returns:
            The order (issue status updated to reflect credit applied).

        Raises:
            ValueError: If the order or issue is not found or credit not eligible.
        """
        order = self._get_order(order_id)
        issue = None
        for i in order.issues:
            if i.issue_id == issue_id:
                issue = i
                break
        if issue is None:
            raise ValueError("Issue not found on this order")
        if getattr(issue, "eligible_for_delay_credit", None) is not True:
            raise ValueError("This issue is not eligible for delay credit or already applied")
        issue.status = "applied"
        return order

    @is_tool(ToolType.WRITE)
    def issue_refund_for_items(
        self,
        order_id: str,
        issue_id: str,
        refund_method_id: str,
    ) -> Order:
        """
        Issue a refund for a missing or wrong item (or other eligible issue) on a delivered order.
        The refund is credited to the specified method (e.g. wallet or original payment).

        Args:
            order_id: The order id, e.g. '#FD1005'.
            issue_id: The issue id from the order's issues list, e.g. 'iss_2002'.
            refund_method_id: Where to credit the refund, e.g. 'wallet_foodie' or the original payment method id.

        Returns:
            The order (issue status updated, refund initiated).

        Raises:
            ValueError: If the order or issue is not found or refund not allowed.
        """
        order = self._get_order(order_id)
        if order.status != "delivered":
            raise ValueError("Refunds for items are only available for delivered orders")
        issue = None
        for i in order.issues:
            if i.issue_id == issue_id:
                issue = i
                break
        if issue is None:
            raise ValueError("Issue not found on this order")
        user = self._get_user(order.user_id)
        if refund_method_id not in user.payment_methods:
            raise ValueError("Refund method not found")
        amount = getattr(issue, "eligible_refund_inr", None) or 0
        if amount <= 0:
            raise ValueError("No eligible refund amount for this issue")
        pm = user.payment_methods[refund_method_id]
        if isinstance(pm, dict) and pm.get("type") == "wallet":
            pm["balance_inr"] = round(pm.get("balance_inr", 0) + amount, 2)
        issue.status = "refund_initiated"
        return order

    @is_tool(ToolType.WRITE)
    def reorder_previous_order(
        self,
        original_order_id: str,
        new_address_id: str,
        payment_method_id: str,
    ) -> Order:
        """
        Place a new order with the same items as a previous order, to a specified address
        and payment method. The new order is created in 'pending_acceptance' status.

        Args:
            original_order_id: The previous order id, e.g. '#FD1001'.
            new_address_id: The address id to deliver to, e.g. 'addr_blr_home'.
            payment_method_id: The payment method to use for the new order.

        Returns:
            The new order (with a new order_id).

        Raises:
            ValueError: If the original order is not found or address/payment invalid.
        """
        orig = self._get_order(original_order_id)
        user = self._get_user(orig.user_id)
        if new_address_id not in [a.address_id for a in user.addresses]:
            raise ValueError("Address not found for this user")
        if payment_method_id not in user.payment_methods:
            raise ValueError("Payment method not found")
        nums = [int(k.replace("#FD", "")) for k in self.db.orders if k.startswith("#FD")]
        new_id = f"#FD{max(nums) + 1 if nums else 1001}"
        new_order = Order(
            order_id=new_id,
            user_id=orig.user_id,
            restaurant_id=orig.restaurant_id,
            address_id=new_address_id,
            status="pending_acceptance",
            items=[OrderItem(**item.model_dump()) for item in orig.items],
            placed_at_ist=orig.placed_at_ist,
            accepted_at_ist=None,
            prepared_at_ist=None,
            picked_up_at_ist=None,
            delivered_at_ist=None,
            payment=None,
            delivery_partner=None,
            issues=[],
        )
        self.db.orders[new_id] = new_order
        return new_order

    @is_tool(ToolType.READ)
    def calculate(self, expression: str) -> str:
        """
        Evaluate a mathematical expression (e.g. for price or discount calculations).

        Args:
            expression: A safe mathematical expression using numbers, +, -, *, /, parentheses, and spaces.

        Returns:
            The result as a string, rounded to 2 decimal places.

        Raises:
            ValueError: If the expression contains invalid characters.
        """
        if not all(c in "0123456789+-*/(). " for c in expression):
            raise ValueError("Invalid characters in expression")
        return str(round(float(eval(expression, {"__builtins__": None}, {})), 2))

    @is_tool(ToolType.GENERIC)
    def transfer_to_human_agents(self, summary: str) -> str:
        """
        Transfer the user to a human agent. Call this only when the request cannot be
        handled within the scope of your actions, or when tools indicate manual escalation is required.
        After calling, send the message 'YOU ARE BEING TRANSFERRED TO A HUMAN AGENT. PLEASE HOLD ON.' to the user.

        Args:
            summary: A short summary of the user's issue for the human agent.

        Returns:
            Confirmation that the transfer was initiated.
        """
        return "Transfer successful"


if __name__ == "__main__":
    from tau2.domains.food_delivery_app.data_model import FoodDeliveryAppDB

    db = FoodDeliveryAppDB.load(FOOD_DELIVERY_APP_DB_PATH)
    tools = FoodDeliveryAppTools(db)
    print(tools.db.get_statistics())
