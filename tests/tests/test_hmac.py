from unittest import TestCase
import hmac


class HMACTest(TestCase):
    def test_kwargs(self):
        """ 1 * G """
        k=b"qwe"
        m=b"ewqwefsdvxc"
        expected = [
            ("sha256", b'\n\xbf\xda\xa3\xb6%u\xa0/\xacp\xbe+\x19?"\x918\x14\xaf\xa6T\xdc\x14\xf21y\xeag\x88EB'),
            ("sha512", b'\x8a\x18\xc1*L3\xeex0c=\xf7A>*\x98\xab$W\xea\xef<Kg\xbc\xc9\x82B-\xf7tM^\xd0\xa9\xb9\xc8zO\x9c4bkWh3\xb2\x1c\x15F9\xd3\xfa\xa8\x9ar\xdd\xba\x9b>\xf1"\xa0p'),
        ]
        for dmod, result in expected:

            res = hmac.new(k, m, dmod).digest()
            self.assertEqual(res, result)

            res = hmac.new(key=k, msg=m, digestmod=dmod).digest()
            self.assertEqual(res, result)

            h = hmac.new(k, digestmod=dmod)
            h.update(m)
            res = h.digest()
            self.assertEqual(res, result)

            h = hmac.new(k, msg=m[:4], digestmod=dmod)
            h.update(m[4:])
            res = h.digest()
            self.assertEqual(res, result)

