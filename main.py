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


# --- Configuration ---

# Uncomment an INPUT_PATH line to experiment with a test file :

#INPUT_PATH = Path("input_image/dog-and-cat.jpg")
#INPUT_PATH = Path("input_image/PDF_TestPage.pdf")


OUTPUT_DIR = Path("output_image")
WATERMARK_TEXT = "Rent renewal"
WATERMARK_SIZE = 40
WATERMARK_ANGLE = 45
WATERMARK_OPACITY = 0.15
WATERMARK_DENSITY = 100

DPI_FOR_RASTERIZATION = 300




def create_text_watermark_pdf(text, size, angle, opacity, page_width, page_height, density):
    """
    Creates a watermark PDF page in memory with repeating angled text bands.
    Returns a BytesIO object that can be read by PyPDF2.
    """
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
    """
    Converts an image file to a PDF in memory (BytesIO object).
    """
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



def apply_watermark_to_pdf(input_pdf_buffer: io.BytesIO, output_filepath: Path, watermark_text: str):
    """
    Applies a text watermark to a PDF document, rasterizing the pages
    to make the watermark harder to remove (now the only option).
    """
    try:
        reader = PdfReader(input_pdf_buffer)
        writer = PdfWriter() # Not strictly needed here, but kept for consistency with PyPDF2 usage pattern
    except Exception as e:
        print(f"Error initializing PdfReader/Writer: {e}")
        return

    if not reader.pages:
        print("Error: Input PDF buffer contains no pages.")
        return

    first_page = reader.pages[0]
    page_width = float(first_page.mediabox.width)
    page_height = float(first_page.mediabox.height)

    watermark_pdf_buffer = create_text_watermark_pdf(
        watermark_text, WATERMARK_SIZE, WATERMARK_ANGLE, WATERMARK_OPACITY,
        page_width, page_height, WATERMARK_DENSITY
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
            print(f"Warning: Could not re-validate PDF structure for page {i+1}: {e}. Skipping this page.")
            continue


    print(f"Attempting to rasterize {len(temp_watermarked_pdf_buffers)} watermarked pages using Ghostscript (this may take a moment)...")
    
    rasterized_image_bytes_list = []
    
    for i, temp_buffer in enumerate(temp_watermarked_pdf_buffers):
        if not temp_buffer.getbuffer().nbytes > 0:
            print(f"Warning: Temporary PDF buffer for page {i+1} is empty after validation, skipping rasterization for this page.")
            continue

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp_input_pdf:
            tmp_input_pdf.write(temp_buffer.getvalue())
            tmp_input_pdf.flush()
            tmp_input_pdf_path = tmp_input_pdf.name

            try:
                gs_command = [
                    "gs",
                    "-dNOPAUSE", "-dBATCH", "-q", "-dSAFER",
                    f"-r{DPI_FOR_RASTERIZATION}",
                    "-sDEVICE=jpeg",
                    "-o", "-", # Output to stdout
                    tmp_input_pdf_path,
                ]
                
                print(f"Running Ghostscript command for page {i+1}: {' '.join(gs_command)}")

                process = subprocess.run(
                    gs_command,
                    capture_output=True,
                    check=True
                )
                
                if process.stderr:
                    print(f"Ghostscript stderr for page {i+1}:\n{process.stderr.decode(errors='ignore')}")

                output_image_buffer_raw = io.BytesIO(process.stdout)
                output_image_buffer_raw.seek(0)
                
                if not output_image_buffer_raw.getbuffer().nbytes > 0:
                    print(f"Error: Ghostscript produced no output for page {i+1}. Check stderr for details.")
                    continue
                    
                try:
                    # Test if Pillow can open it and get dimensions
                    img = Image.open(output_image_buffer_raw)
                    img.verify() # Verify image integrity
                    output_image_buffer_raw.seek(0) # Reset buffer after verify
                except Image.UnidentifiedImageError as image_error:
                    print(f"Error: Pillow could not identify image from Ghostscript output for page {i+1}: {image_error}")
                    debug_output_path = output_filepath.parent / f"debug_gs_output_page_{i+1}.bin"
                    with open(debug_output_path, "wb") as f_debug:
                        f_debug.write(process.stdout)
                    print(f"Ghostscript's raw stdout for page {i+1} saved to: {debug_output_path}. Inspect this file.")
                    continue
                except Exception as img_check_error:
                     print(f"Error verifying image from Ghostscript output for page {i+1}: {img_check_error}")
                     output_image_buffer_raw.seek(0) # Reset buffer
                     continue

                if img.width <= 10 and img.height <= 10:
                    print(f"Warning: Rasterized image for page {i+1} is suspiciously small ({img.width}x{img.height} pixels). "
                          "This often indicates a Ghostscript rendering error. Skipping this page.")
                    continue
                    
                print(f"Rasterized page {i+1}: {img.width}x{img.height} pixels (format: {img.format}).")
                
                # Append a NEW BytesIO object containing the raw JPEG data
                # This ensures img2pdf gets a clean, unconsumed stream.
                rasterized_image_bytes_list.append(io.BytesIO(output_image_buffer_raw.getvalue()))
                
            except subprocess.CalledProcessError as e:
                print(f"Error during Ghostscript rasterization of page {i+1} (exit code {e.returncode}):")
                if e.stdout:
                    print(f"Ghostscript stdout:\n{e.stdout.decode(errors='ignore')}")
                if e.stderr:
                    print(f"Ghostscript stderr:\n{e.stderr.decode(errors='ignore')}")
                print("Check Ghostscript installation and ensure it's in your system's PATH.")
            except Exception as e:
                print(f"Error during image processing after Ghostscript for page {i+1}: {e}")

    print(f"Finished rasterization. Total valid images prepared for final PDF: {len(rasterized_image_bytes_list)}")

    if not rasterized_image_bytes_list:
        raise RuntimeError("No valid images were generated after rasterization. Cannot create output PDF. Check DPI, source content, and Ghostscript installation.")

    output_filepath.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(output_filepath, "wb") as f:
            f.write(img2pdf.convert(rasterized_image_bytes_list))
        print(f"Successfully watermarked PDF (rasterized) saved to: {output_filepath}")
    except Exception as e:
        print(f"Error during final img2pdf conversion: {e}")
        raise


# --- Main Processing Logic ---

def process_file_with_watermark(input_filepath: Path, output_dir: Path, watermark_text: str):
    """
    Main function to process either an image or PDF file,
    convert it to PDF if it's an image, and then apply a watermark.
    """
    if not input_filepath.exists():
        print(f"Error: Input file not found at {input_filepath}")
        return

    # output_pdf_name = f"{input_filepath.stem}_watermarked.pdf" 
    output_pdf_name = f"{input_filepath.stem}_watermarked_rasterized.pdf"
    output_pdf_filepath = output_dir / output_pdf_name

    input_is_pdf = False
    mime_type, _ = mimetypes.guess_type(input_filepath)

    if mime_type == 'application/pdf':
        input_is_pdf = True
    elif mime_type and mime_type.startswith('image/'):
        input_is_pdf = False
    else:
        try:
            Image.open(input_filepath)
            input_is_pdf = False
            print(f"Warning: MIME type for {input_filepath} unknown, but successfully opened as image.")
        except Exception:
            print(f"Error: {input_filepath} is neither a recognized image nor a PDF.")
            return

    pdf_buffer_to_watermark = None

    if input_is_pdf:
        try:
            with open(input_filepath, "rb") as f:
                pdf_buffer_to_watermark = io.BytesIO(f.read())
            print(f"Loading PDF '{input_filepath.name}' for watermarking.")
        except Exception as e:
            print(f"Error reading PDF file {input_filepath}: {e}")
            return
    else: # It's an image
        try:
            pdf_buffer_to_watermark = convert_image_to_pdf_buffer(input_filepath)
        except IOError as e:
            print(e)
            return

    if pdf_buffer_to_watermark:
        apply_watermark_to_pdf(pdf_buffer_to_watermark, output_pdf_filepath, watermark_text)

# --- Execute Script ---
if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Processing '{INPUT_PATH.name}' with watermark '{WATERMARK_TEXT}'...")
    process_file_with_watermark(INPUT_PATH, OUTPUT_DIR, WATERMARK_TEXT)