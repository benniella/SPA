"""Password hashing and policy.

The hasher is the only thing standing between a database leak and every
credential, so these assert the properties that make that true rather than the
algorithm's internals.
"""

from __future__ import annotations

from app.domain.users.credentials import PasswordPolicy, normalise_email, normalise_phone
from app.infrastructure.security.passwords import Pbkdf2PasswordHasher


class TestPasswordPolicy:
    def test_a_strong_password_satisfies_the_policy(self) -> None:
        assert PasswordPolicy().is_satisfied_by("correct-horse-9")

    def test_a_short_password_is_rejected(self) -> None:
        assert not PasswordPolicy().is_satisfied_by("short1")

    def test_a_password_without_a_digit_is_rejected(self) -> None:
        assert not PasswordPolicy().is_satisfied_by("onlyletters")

    def test_a_password_without_a_letter_is_rejected(self) -> None:
        assert not PasswordPolicy().is_satisfied_by("1234567890")

    def test_every_broken_rule_is_reported(self) -> None:
        violations = PasswordPolicy().violations("abc")
        assert len(violations) == 2


class TestPbkdf2PasswordHasher:
    def test_a_password_verifies_against_its_own_hash(self) -> None:
        hasher = Pbkdf2PasswordHasher()
        stored = hasher.hash("correct-horse-9")
        assert hasher.verify("correct-horse-9", stored)

    def test_a_wrong_password_does_not_verify(self) -> None:
        hasher = Pbkdf2PasswordHasher()
        stored = hasher.hash("correct-horse-9")
        assert not hasher.verify("something-else-1", stored)

    def test_the_plaintext_never_appears_in_the_stored_value(self) -> None:
        hasher = Pbkdf2PasswordHasher()
        stored = hasher.hash("correct-horse-9")
        assert "correct-horse-9" not in stored

    def test_the_same_password_hashes_differently_each_time(self) -> None:
        hasher = Pbkdf2PasswordHasher()
        assert hasher.hash("correct-horse-9") != hasher.hash("correct-horse-9")

    def test_a_malformed_stored_hash_does_not_raise(self) -> None:
        hasher = Pbkdf2PasswordHasher()
        assert not hasher.verify("correct-horse-9", "not-a-real-hash")


class TestNormalisation:
    def test_email_is_lower_cased_and_trimmed(self) -> None:
        assert normalise_email("  Coach@Club.Example  ") == "coach@club.example"

    def test_email_plus_tags_are_preserved(self) -> None:
        assert normalise_email("coach+video@club.example") == "coach+video@club.example"

    def test_phone_formatting_is_stripped(self) -> None:
        assert normalise_phone("+44 7700 900123") == "+447700900123"

    def test_phone_without_a_country_code_keeps_its_digits(self) -> None:
        assert normalise_phone("07700 900123") == "07700900123"
