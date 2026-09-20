import unittest

from reconcile_acceptance import confirmed_partial


class PartialBillingTests(unittest.TestCase):
    def setUp(self):
        self.event = dict(request_id='r', upstream_client_request_id='u', region='us',
                          api_key_id='key-hmac-v1:fixture', success=False, usage_reported=True,
                          input_tokens=0, output_tokens=0, cache_hit_tokens=0)
        self.bill = dict(input_tokens=62, output_tokens=4096, cache_read_tokens=0)
        self.audit = dict(request_id='r', upstream_client_request_id='u', region='us',
                          api_key_id='key-hmac-v1:fixture', stage='request_canceled',
                          response_complete=False)

    def test_observed_zero_prefix_requires_correlated_cancellation(self):
        self.assertTrue(confirmed_partial(self.event, self.bill, [self.audit]))
        self.assertFalse(confirmed_partial(self.event, self.bill, []))
        for field in ('request_id', 'upstream_client_request_id', 'region', 'api_key_id'):
            with self.subTest(field=field):
                self.assertFalse(confirmed_partial(self.event, self.bill,
                                                 [dict(self.audit, **{field: 'other'})]))

    def test_complete_unknown_or_excess_usage_is_not_excused(self):
        for change in (dict(success=True), dict(usage_reported=False),
                       dict(input_tokens=63), dict(output_tokens=4097),
                       dict(cache_hit_tokens=1), dict(upstream_client_request_id='')):
            with self.subTest(change=change):
                self.assertFalse(confirmed_partial(dict(self.event, **change), self.bill, [self.audit]))
        for change in (dict(response_complete=True), dict(stage='upstream_failed'),
                       dict(stage='upstream_completed')):
            with self.subTest(change=change):
                self.assertFalse(confirmed_partial(self.event, self.bill, [dict(self.audit, **change)]))
        self.assertFalse(confirmed_partial(self.event, self.bill, [self.audit, self.audit]))

    def test_known_nonzero_prefix_and_image_columns(self):
        event = dict(self.event, input_tokens=71, output_tokens=16, cache_hit_tokens=8)
        bill = dict(input_tokens=60, image_input_tokens=3, cache_read_tokens=8,
                    output_tokens=0, image_output_tokens=32)
        self.assertTrue(confirmed_partial(event, bill, [self.audit]))
        self.assertFalse(confirmed_partial(dict(event, output_tokens=33), bill, [self.audit]))


if __name__ == '__main__':
    unittest.main()
