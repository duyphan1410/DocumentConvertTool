"""
Unit tests for Vietnamese Fuzzy Matcher Engine.
Author: Huy (PKB Phase 1 - v1.10.0)
"""
import unittest
from src.services.fuzzy_matcher import (
    normalize_vietnamese,
    tokenize_vietnamese,
    calculate_similarity,
    rank_candidates,
    resolve_candidate,
    find_fuzzy_substring_occurrences,
)
from src.services.link_parser import find_unlinked_mentions


class TestVietnameseFuzzyMatcher(unittest.TestCase):

    def test_normalize_vietnamese_diacritics(self):
        self.assertEqual(normalize_vietnamese("Báo cáo quy trình"), "bao cao quy trinh")
        self.assertEqual(normalize_vietnamese("Đề án Đổi mới Điểm số"), "de an doi moi diem so")
        self.assertEqual(normalize_vietnamese("Trí Tuệ Nhân Tạo & Học Máy"), "tri tue nhan tao hoc may")
        self.assertEqual(normalize_vietnamese("   [Tài liệu]  #Hướng-dẫn!  "), "tai lieu huong dan")

    def test_tokenize_vietnamese(self):
        tokens = tokenize_vietnamese("Đề án: Phát triển Trí Tuệ Nhân Tạo!")
        self.assertEqual(tokens, ["de", "an", "phat", "trien", "tri", "tue", "nhan", "tao"])

    def test_calculate_similarity_exact_and_normalized(self):
        # Exact match
        self.assertEqual(calculate_similarity("Báo cáo", "Báo cáo"), 1.0)
        # Normalized match (same accents stripped)
        self.assertGreaterEqual(calculate_similarity("Báo cáo quy trình", "bao cao quy trinh"), 0.95)
        self.assertGreaterEqual(calculate_similarity("Đề án 2026", "de an 2026"), 0.95)

    def test_calculate_similarity_token_reordering(self):
        # Word order variation
        score = calculate_similarity("Kế hoạch phát triển AI", "Phát triển AI kế hoạch")
        self.assertGreaterEqual(score, 0.85)

    def test_calculate_similarity_prefix_and_partial(self):
        # Prefix typing during autocomplete
        score = calculate_similarity("bao cao", "Báo cáo tài chính quý 3")
        self.assertGreaterEqual(score, 0.80)

    def test_rank_candidates(self):
        candidates = [
            "Báo cáo quy trình",
            "Kế hoạch tài chính 2026",
            "Đề án chuyển đổi số",
            "Hướng dẫn đào tạo AI",
            "Quy trình bảo mật",
        ]
        
        # Searching "chuyen doi so" should rank "Đề án chuyển đổi số" highest
        ranked = rank_candidates("chuyen doi so", candidates)
        self.assertTrue(len(ranked) > 0)
        self.assertEqual(ranked[0][0], "Đề án chuyển đổi số")
        self.assertGreaterEqual(ranked[0][1], 0.85)

        # Searching "bao cao" should rank "Báo cáo quy trình" highest
        ranked2 = rank_candidates("bao cao", candidates)
        self.assertEqual(ranked2[0][0], "Báo cáo quy trình")

    def test_resolve_candidate(self):
        candidates = ["Tài liệu hướng dẫn", "Báo cáo doanh thu", "Đề án AI"]
        best = resolve_candidate("tai lieu huong dan", candidates)
        self.assertEqual(best, "Tài liệu hướng dẫn")

        best_d = resolve_candidate("de an ai", candidates)
        self.assertEqual(best_d, "Đề án AI")

        none_match = resolve_candidate("hoan toan khac", candidates, threshold=0.8)
        self.assertIsNone(none_match)

    def test_find_fuzzy_substring_occurrences(self):
        text = "Vui lòng xem qua de an chuyen doi so trước cuộc họp ngày mai."
        target = "Đề án chuyển đổi số"
        occurrences = find_fuzzy_substring_occurrences(text, target, min_similarity=0.85)
        self.assertEqual(len(occurrences), 1)
        self.assertEqual(occurrences[0][2], "de an chuyen doi so")
        self.assertGreaterEqual(occurrences[0][3], 0.90)

    def test_find_unlinked_mentions_with_vietnamese_fuzzy(self):
        doc_text = """# Biên bản cuộc họp
1. Hôm nay chúng ta thảo luận về bao cao quy trinh mới.
2. Tham khảo thêm ghi chú đã link: [[Báo cáo quy trình]].
3. Xem lại bản nháp de an chuyen doi so trước 5h chiều.
"""
        # Search unlinked mentions for "Báo cáo quy trình"
        mentions = find_unlinked_mentions(doc_text, "Báo cáo quy trình")
        # Should find "bao cao quy trinh" on line 1, but skip line 2 because it's inside [[...]]
        self.assertEqual(len(mentions), 1)
        self.assertEqual(mentions[0].matched_text, "bao cao quy trinh")

        # Search unlinked mentions for "Đề án chuyển đổi số"
        mentions_dean = find_unlinked_mentions(doc_text, "Đề án chuyển đổi số")
        self.assertEqual(len(mentions_dean), 1)
        self.assertEqual(mentions_dean[0].matched_text, "de an chuyen doi so")


if __name__ == "__main__":
    unittest.main()
