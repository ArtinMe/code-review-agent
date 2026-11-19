from dataclasses import dataclass, field
from decimal import Decimal


class InsufficientFunds(Exception):
    pass


@dataclass
class Account:
    owner: str
    balance: Decimal = Decimal("0")
    history: list[Decimal] = field(default_factory=list)

    def deposit(self, amount: Decimal) -> None:
        if amount <= 0:
            raise ValueError("Deposit must be positive")
        self.balance += amount
        self.history.append(amount)

    def withdraw(self, amount: Decimal) -> None:
        if amount <= 0:
            raise ValueError("Withdrawal must be positive")
        if amount > self.balance:
            raise InsufficientFunds(f"{self.owner} has {self.balance}")
        self.balance -= amount
        self.history.append(-amount)
