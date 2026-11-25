"""GSTIN / PAN / IFSC / account-number validator tests (incl. mod-36 check digit)."""
from django.test import TestCase

from vendors.services import (gstin_checksum, is_valid_account_number, is_valid_gstin,
                              is_valid_ifsc, is_valid_pan)


class GSTINValidatorTests(TestCase):
    # Known-good GSTIN: state 27 + PAN AAACS1234F + entity P + Z + computed digit.
    def test_valid_gstin_passes(self):
        self.assertTrue(is_valid_gstin('27AAACS1234FPZ4'))

    def test_company_gstin_passes(self):
        self.assertTrue(is_valid_gstin('27AABCT1234A1Z0'))

    def test_checksum_is_mod36(self):
        gstin = '27AAACS1234FPZ4'
        self.assertEqual(gstin_checksum(gstin[:14]), gstin[14])

    def test_wrong_check_digit_fails(self):
        self.assertFalse(is_valid_gstin('27AAACS1234FPZ5'))
        self.assertFalse(is_valid_gstin('27AABCT1234A1Z5'))  # made-up digit

    def test_bad_format_fails(self):
        # too short, entity code '1', missing 'Z', empty
        self.assertFalse(is_valid_gstin('27AAACS1234FPZ'))
        self.assertFalse(is_valid_gstin('27AAACS1234F1Z4'))
        self.assertFalse(is_valid_gstin('27AAACS1234FPA4'))
        self.assertFalse(is_valid_gstin(''))
        self.assertFalse(is_valid_gstin(None))

    def test_embedded_pan_must_be_valid(self):
        self.assertFalse(is_valid_gstin('27AAAC11234FPZ4'))  # PAN 5th char must be a letter

    def test_state_codes(self):
        self.assertTrue(is_valid_gstin('29AACCT9012PPZ4'))   # Karnataka
        self.assertTrue(is_valid_gstin('07AAGFM5678KPZ1'))   # Delhi


class PANValidatorTests(TestCase):
    def test_valid_pan(self):
        self.assertTrue(is_valid_pan('AAACS1234F'))
        self.assertTrue(is_valid_pan('AABCT1234A'))

    def test_invalid_pan(self):
        self.assertFalse(is_valid_pan('AAACS1234F1'))   # 11 chars
        self.assertFalse(is_valid_pan('1234F5678A'))    # wrong structure
        self.assertFalse(is_valid_pan('AAAC S1234F'))   # space
        self.assertFalse(is_valid_pan(''))


class IFSCValidatorTests(TestCase):
    def test_valid_ifsc(self):
        self.assertTrue(is_valid_ifsc('HDFC0001234'))
        self.assertTrue(is_valid_ifsc('KKBK0007788'))

    def test_invalid_ifsc(self):
        self.assertFalse(is_valid_ifsc('HDFC1001234'))  # 5th char must be 0
        self.assertFalse(is_valid_ifsc('HDFC000123'))   # too short
        self.assertFalse(is_valid_ifsc('12340001234'))  # bank code not letters


class AccountNumberValidatorTests(TestCase):
    def test_valid(self):
        self.assertTrue(is_valid_account_number('12345678901'))

    def test_invalid(self):
        self.assertFalse(is_valid_account_number('12345'))       # too short
        self.assertFalse(is_valid_account_number('1234ABCD901')) # letters
