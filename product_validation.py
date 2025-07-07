from dataclasses import dataclass

@dataclass
class Product:
    name: str
    price: float
    quantity: int

    def __post_init__(self):
        if not isinstance(self.name, str):
            raise TypeError(f"Expected 'name' to be a string, got {type(self.name).__name__}")
        if not isinstance(self.price, (int, float)):
            raise TypeError(f"Expected 'price' to be a number, got {type(self.price).__name__}")
        if not isinstance(self.quantity, int):
            raise TypeError(f"Expected 'quantity' to be an integer, got {type(self.quantity).__name__}")
        if self.price < 0:
            raise ValueError("Price cannot be negative.")
        if self.quantity < 0:
            raise ValueError("Quantity cannot be negative.")

# Valid usage
try:
    p1 = Product(name="Laptop", price=1200.50, quantity=10)
    print(p1)
except (TypeError, ValueError) as e:
    print(f"Error creating product: {e}")

print("-" * 20)

# Invalid type for price
try:
    p2 = Product(name="Mouse", price="fifty", quantity=5)
    print(p2)
except (TypeError, ValueError) as e:
    print(f"Error creating product: {e}")

print("-" * 20)

# Invalid value for quantity
try:
    p3 = Product(name="Keyboard", price=75.00, quantity=-2)
    print(p3)
except (TypeError, ValueError) as e:
    print(f"Error creating product: {e}")
