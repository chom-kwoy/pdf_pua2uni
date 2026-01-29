import fitz  # PyMuPDF
import argparse
from puatable import PUA_CONV_TAB

def pua_to_uni(s: str) -> str:
    """
    Converts PUA characters back into their Unicode sequences.
    """
    return "".join([PUA_CONV_TAB.get(ch, ch) for ch in s])

def make_text_unselectable(input_path, output_path):
    src_doc = fitz.open(input_path)
    out_doc = fitz.open()

    print(f"Processing {len(src_doc)} pages...")

    for page in src_doc:
        # 1. Get SVG image of the page
        # text_as_path=True forces text to be converted to geometric curves
        svg_text = page.get_svg_image(text_as_path=True)

        # 2. Open the SVG data as a temporary document
        # We must encode to utf-8 to pass it as a stream
        svg_doc = fitz.open(stream=svg_text.encode("utf-8"), filetype="svg")

        # 3. Convert the SVG document to a PDF stream (in memory)
        # This creates a vector-based PDF representation of the SVG
        pdf_bytes = svg_doc.convert_to_pdf()

        # 4. Open this new in-memory PDF
        vector_pdf_doc = fitz.open("pdf", pdf_bytes)

        # 5. Create a blank page in the output document with the same dimensions
        new_page = out_doc.new_page(width=page.rect.width, height=page.rect.height)

        # 6. Overlay the vector graphics onto the new page
        # show_pdf_page places the vector_pdf_doc onto new_page
        new_page.show_pdf_page(page.rect, vector_pdf_doc, 0)

    out_doc.save(output_path)
    print(f"Saved unselectable PDF to: {output_path}")

def fix_with_html_engine(input_pdf, unselectable_pdf, output_pdf, do_display):
    doc = fitz.open(input_pdf)
    unselectable_doc = fitz.open(unselectable_pdf)
    # Path must be absolute for the HTML engine
    font_path = "./NotoSansKR-Regular.ttf"

    for page, upage in zip(doc, unselectable_doc):
        dict_data = page.get_text("dict")

        for block in dict_data.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    original_text = span["text"]

                    # 1. Redact original (removes old encoding, keeps visual)
                    rect = fitz.Rect(span["bbox"])
                    fontsize = span['size'] * 1.1

                    # 2. Create HTML for advanced shaping
                    # We use @font-face to ensure GSUB/OpenType features are invoked
                    html_header = f"""
                    <style>
                        @font-face {{
                            font-family: 'NotoSans';
                            src: url('{font_path}');
                        }}
                        p {{
                            font-family: 'NotoSans';
                            color: {'#0000FF' if do_display else '#0000FF01'};
                            margin: 0;
                            padding: 0;
                            line-height: 1;
                        }}
                    </style>
                    """
                    html_content = ""
                    for ch in original_text:
                        fixed_ch = pua_to_uni(ch)
                        for c in fixed_ch:
                            html_content += f'<span style="font-size: {fontsize / len(fixed_ch)}pt">{c}</span>&#8203;'

                    # 3. Insert the HTML into the rect
                    upage.insert_htmlbox(rect, f'{html_header}<p>{html_content}</p>')

    unselectable_doc.save(output_pdf, garbage=4, deflate=True)
    unselectable_doc.close()

def print_text(output_pdf):
    doc = fitz.open(output_pdf)

    for page in doc:
        dict_data = page.get_text("dict")

        for block in dict_data.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    print(span['text'])

    doc.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Replace PUA OCR text with Unicode in a PDF.")

    # Adding the arguments
    parser.add_argument("-i", "--input", required=True, help="Path to the input PDF file")
    parser.add_argument("-o", "--output", required=True, help="Path to save the output PDF")
    parser.add_argument("-d", "--display", action='store_true', help="display overlayed text")

    args = parser.parse_args()

    # Execute the transformation
    make_text_unselectable(args.input, "tmp.pdf")
    fix_with_html_engine(args.input, "tmp.pdf", args.output, args.display)
    # print_text(args.output)
