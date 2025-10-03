import img2pdf
from PIL import Image
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import Color
import io
from pathlib import Path
import mimetypes
import subprocess
import tempfile
import argparse
import sys


# --- Configuration Defaults ---
OUTPUT_DIR = Path("output_image")
WATERMARK_TEXT = "Contract renewal Agency XYZ 010125"
WATERMARK_SIZE = 20
WATERMARK_ANGLE = 45
WATERMARK_OPACITY = 0.15
WATERMARK_DENSITY = 100
DPI_FOR_RASTERIZATION = 300


def create_text_watermark_pdf(text, size, angle, opacity, page_width, page_height, density):
    """Creates a watermark PDF page in memory with repeating angled text bands."""
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=(page_width, page_height))

    watermark_color = Color(0, 0, 0, alpha=opacity)
    c.setFillColor(watermark_color)
    c.setFont("Helvetica-Bold", size)

    text_width_estimate = size * len(text) * 0.6
    step_x = text_width_estimate * (density / 100.0)
    step_y = size * 2.0 * (density / 100.0)

    max_dim = max(page_width, page_height) * 1.5

    c.saveState()
    c.translate(page_width / 2, page_height / 2)
    c.rotate(angle)

    for x_offset in range(int(-max_dim / 2), int(max_dim / 2), int(step_x)):
        for y_offset in range(int(-max_dim / 2), int(max_dim / 2), int(step_y)):
            c.drawCentredString(x_offset, y_offset, text)
    c.restoreState()

    c.showPage()
    c.save()
    packet.seek(0)
    return packet


def convert_image_to_pdf_buffer(image_filepath: Path) -> io.BytesIO:
    """Converts an image file to a PDF in memory (BytesIO object)."""
    try:
        img = Image.open(image_filepath)

        img_byte_arr = io.BytesIO()
        img_format = img.format if img.format else 'JPEG'
        if img_format == 'MPO':
            img_format = 'JPEG'
        img.save(img_byte_arr, format=img_format)
        img_byte_arr.seek(0)

        pdf_buffer = io.BytesIO()
        pdf_buffer.write(img2pdf.convert(img_byte_arr))
        pdf_buffer.seek(0)
        print(f"Image '{image_filepath.name}' converted to PDF buffer.")
        return pdf_buffer
    except Exception as e:
        raise IOError(f"Error converting image to PDF: {e}")


def apply_watermark_to_pdf(input_pdf_buffer: io.BytesIO, output_filepath: Path,
                           watermark_text: str, size: int, angle: int,
                           opacity: float, density: int, dpi: int):
    """Applies a text watermark to a PDF document and rasterizes the result."""
    try:
        reader = PdfReader(input_pdf_buffer)
    except Exception as e:
        print(f"Error initializing PdfReader: {e}")
        return

    if not reader.pages:
        print("Error: Input PDF buffer contains no pages.")
        return

    first_page = reader.pages[0]
    page_width = float(first_page.mediabox.width)
    page_height = float(first_page.mediabox.height)

    watermark_pdf_buffer = create_text_watermark_pdf(
        watermark_text, size, angle, opacity,
        page_width, page_height, density
    )
    watermark_page = PdfReader(watermark_pdf_buffer).pages[0]

    temp_watermarked_pdf_buffers = []
    for i, page in enumerate(reader.pages):
        temp_writer = PdfWriter()
        temp_writer.add_page(page)
        temp_writer.pages[-1].merge_page(watermark_page)

        page_output_buffer = io.BytesIO()
        temp_writer.write(page_output_buffer)
        page_output_buffer.seek(0)
        
        try:
            validated_reader = PdfReader(page_output_buffer)
            validated_buffer = io.BytesIO()
            validated_writer = PdfWriter()
            for p in validated_reader.pages:
                validated_writer.add_page(p)
            validated_writer.write(validated_buffer)
            validated_buffer.seek(0)
            temp_watermarked_pdf_buffers.append(validated_buffer)
        except Exception as e:
            print(f"Warning: Could not re-validate page {i+1}: {e}")
            continue

    print(f"Rasterizing {len(temp_watermarked_pdf_buffers)} pages using Ghostscript...")

    rasterized_image_bytes_list = []
    for i, temp_buffer in enumerate(temp_watermarked_pdf_buffers):
        if not temp_buffer.getbuffer().nbytes > 0:
            continue

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp_input_pdf:
            tmp_input_pdf.write(temp_buffer.getvalue())
            tmp_input_pdf.flush()
            tmp_input_pdf_path = tmp_input_pdf.name

            try:
                gs_command = [
                    "gs",
                    "-dNOPAUSE", "-dBATCH", "-q", "-dSAFER",
                    f"-r{dpi}",
                    "-sDEVICE=jpeg",
                    "-o", "-",
                    tmp_input_pdf_path,
                ]
                process = subprocess.run(gs_command, capture_output=True, check=True)

                output_image_buffer_raw = io.BytesIO(process.stdout)
                output_image_buffer_raw.seek(0)

                img = Image.open(output_image_buffer_raw)
                img.verify()
                output_image_buffer_raw.seek(0)

                rasterized_image_bytes_list.append(io.BytesIO(output_image_buffer_raw.getvalue()))
                print(f"Rasterized page {i+1}: {img.width}x{img.height} pixels")

            except Exception as e:
                print(f"Error rasterizing page {i+1}: {e}")

    if not rasterized_image_bytes_list:
        raise RuntimeError("No valid images were generated after rasterization.")

    output_filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(output_filepath, "wb") as f:
        f.write(img2pdf.convert(rasterized_image_bytes_list))
    print(f"Watermarked PDF saved to: {output_filepath}")


def process_file_with_watermark(input_filepath: Path, output_dir: Path,
                                text: str, size: int, angle: int,
                                opacity: float, density: int, dpi: int):
    """Processes either an image or PDF file, then applies a watermark."""
    if not input_filepath.exists():
        print(f"Error: Input file not found at {input_filepath}")
        return

    output_pdf_name = f"{input_filepath.stem}_watermarked_rasterized.pdf"
    output_pdf_filepath = output_dir / output_pdf_name

    mime_type, _ = mimetypes.guess_type(input_filepath)
    input_is_pdf = mime_type == 'application/pdf'

    if not input_is_pdf and (not mime_type or not mime_type.startswith('image/')):
        try:
            Image.open(input_filepath)
            input_is_pdf = False
        except Exception:
            print(f"Error: {input_filepath} is neither image nor PDF.")
            return

    if input_is_pdf:
        with open(input_filepath, "rb") as f:
            pdf_buffer = io.BytesIO(f.read())
    else:
        pdf_buffer = convert_image_to_pdf_buffer(input_filepath)

    apply_watermark_to_pdf(pdf_buffer, output_pdf_filepath,
                           text, size, angle, opacity, density, dpi)


# --- Command-line Interface ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Apply a rasterized watermark to image(s) or PDF(s)."
    )
    parser.add_argument(
        "input_files", type=Path, nargs="+",
        help="Path(s) to input image(s) or PDF(s)"
    )
    parser.add_argument("-o", "--output-dir", type=Path, default=OUTPUT_DIR,
                        help=f"Output directory (default: {OUTPUT_DIR})")
    parser.add_argument("-t", "--text", type=str, default=WATERMARK_TEXT,
                        help=f"Watermark text (default: '{WATERMARK_TEXT}')")
    parser.add_argument("-s", "--size", type=int, default=WATERMARK_SIZE,
                        help=f"Font size of watermark text (default: {WATERMARK_SIZE})")
    parser.add_argument("-a", "--angle", type=int, default=WATERMARK_ANGLE,
                        help=f"Rotation angle of watermark text (default: {WATERMARK_ANGLE})")
    parser.add_argument("-p", "--opacity", type=float, default=WATERMARK_OPACITY,
                        help=f"Opacity of watermark text (0.0–1.0, default: {WATERMARK_OPACITY})")
    parser.add_argument("-d", "--density", type=int, default=WATERMARK_DENSITY,
                        help=f"Density of watermark repetition (default: {WATERMARK_DENSITY})")
    parser.add_argument("--dpi", type=int, default=DPI_FOR_RASTERIZATION,
                        help=f"DPI for Ghostscript rasterization (default: {DPI_FOR_RASTERIZATION})")

    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    for input_file in args.input_files:
        print("=" * 60)
        print(f"Starting processing: {input_file.name}")
        try:
            process_file_with_watermark(
                input_file, args.output_dir,
                args.text, args.size, args.angle,
                args.opacity, args.density, args.dpi
            )
            print(f"Finished: {input_file.name}")
        except Exception as e:
            print(f"Error processing {input_file.name}: {e}")
        print("=" * 60 + "\n")
