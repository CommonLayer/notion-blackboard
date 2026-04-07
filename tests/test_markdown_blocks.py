import unittest

from notion.markdown_blocks import markdown_to_notion_blocks, markdown_to_preview, notion_blocks_to_markdown


class MarkdownBlocksTest(unittest.TestCase):
    def test_markdown_roundtrip_preserves_basic_structure(self) -> None:
        markdown = (
            "# Title\n\n"
            "## Key Findings\n\n"
            "- **First** point\n"
            "- Second point\n\n"
            "A paragraph with a [link](https://example.com).\n"
        )

        blocks = markdown_to_notion_blocks(markdown)
        rebuilt = notion_blocks_to_markdown(blocks)

        self.assertTrue(any(block["type"] == "heading_1" for block in blocks))
        self.assertTrue(any(block["type"] == "bulleted_list_item" for block in blocks))
        self.assertIn("# Title", rebuilt)
        self.assertIn("- **First** point", rebuilt)
        self.assertIn("[link](https://example.com)", rebuilt)

    def test_preview_uses_first_readable_line(self) -> None:
        markdown = "# Title\n\n## Goal\n\nA concise summary line.\n\n- Detail\n"
        self.assertEqual(markdown_to_preview(markdown), "A concise summary line.")


if __name__ == "__main__":
    unittest.main()
