import unittest

from bizdir_crawler.parsing import parse_detail_payload


DETAIL_WITH_CITY_PROVINCE = """
<ul>
  <li><strong>Company Name</strong>: <span itemprop='name'>A-lign dental clinic</span></li>
  <li><strong>City/Province</strong>: <span itemprop='location'>361-831 - KR</span></li>
  <li><strong>Country</strong>: <span itemprop='location'>South Korea</span></li>
  <li><strong>Address</strong>: <span itemprop='address'>140-10, Sachang-dong Heungduk-gu Chongju City,Chun</span></li>
  <li><strong>Contact</strong>: <span itemprop='contactPoint'>Jae-Joon,Lee</span></li>
  <li><strong>Website</strong>: <a href='http://orthowell.com' itemprop='url' rel='nofollow'>orthowell.com</a></li>
  <li><strong>Area</strong>: <span itemprop='employees'><a href="/taxonomy/term/39">Chongju</a></span></li>
</ul>
"""


class ParsingTests(unittest.TestCase):
    def test_parse_detail_payload_ignores_city_province_when_extracting_company_name(self):
        row = parse_detail_payload(DETAIL_WITH_CITY_PROVINCE, "https://kor.bizdirlib.com/node/90620")

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row.company_name, "A-lign dental clinic")
        self.assertEqual(row.contact, "Jae-Joon,Lee")
        self.assertEqual(row.website, "orthowell.com")
        self.assertEqual(row.area, "Chongju")


if __name__ == "__main__":
    unittest.main()
