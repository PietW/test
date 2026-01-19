import os
import time
import fitz  # PyMuPDF
import pypdf
from PIL import Image
import io
import datetime
import json
import re # For cleaning pypdf visitor output

# --- Optional Imports (handle gracefully if libraries not installed) ---
try:
    import pytesseract
    from pdf2image import convert_from_path
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False
    print("Warning: pytesseract or pdf2image not found. OCR method will be unavailable.")

try:
    from unstructured.partition.pdf import partition_pdf
    UNSTRUCTURED_AVAILABLE = True
except ImportError:
    UNSTRUCTURED_AVAILABLE = False
    print("Warning: unstructured not found. Unstructured methods will be unavailable.")

# pypdfium2 might be used by pdf2image or pymupdf4llm internally
try:
    import pypdfium2
except ImportError:
    print("Warning: pypdfium2 not found. This might affect pdf2image or pymupdf4llm functionality.")
    pass

# --- pymupdf4llm Import ---
try:
    from pymupdf4llm import to_markdown as pymupdf4llm_to_markdown
    PYMUPDF4LLM_AVAILABLE = True
except ImportError:
    PYMUPDF4LLM_AVAILABLE = False
    print("Warning: pymupdf4llm not found. pymupdf4llm method will be unavailable.")

# --- NEW: AlcheMark AI Import ---
try:
    from alchemark_ai import pdf2md as alchemark_pdf2md
    # from alchemark_ai.utils.formatted_result import FormattedResult # Only if type hinting is strictly needed
    ALCHEMARK_AVAILABLE = True
    print("AlcheMark AI library found.")
except ImportError:
    ALCHEMARK_AVAILABLE = False
    print("Warning: alchemark-ai not found. AlcheMark AI method will be unavailable. Install with 'pip install alchemark-ai'")


# --- Existing Extraction Functions ---

def extract_text_pypdf(pdf_path):
    """Extracts text using the pypdf library."""
    text = ""
    try:
        reader = pypdf.PdfReader(pdf_path)
        for page in reader.pages:
            text += page.extract_text() or ""
    except Exception as e:
        print(f"Error processing {pdf_path} with pypdf: {e}")
        return None
    return text

def extract_text_pymupdf(pdf_path):
    """Extracts text using the PyMuPDF (fitz) library."""
    text = ""
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            text += page.get_text() or ""
        doc.close()
    except Exception as e:
        print(f"Error processing {pdf_path} with PyMuPDF: {e}")
        return None
    return text

def extract_text_ocr(pdf_path):
    """Extracts text using Tesseract OCR via pdf2image and pytesseract."""
    if not PYTESSERACT_AVAILABLE:
        print("OCR method skipped: pytesseract or pdf2image not available.")
        return None
    text = ""
    try:
        images = convert_from_path(pdf_path) # Add poppler_path if needed
        for i, img in enumerate(images):
            try:
                page_text = pytesseract.image_to_string(img)
                text += page_text + "\n"
            except pytesseract.TesseractNotFoundError:
                 print("Error: Tesseract executable not found or not in PATH.")
                 print("Ensure Tesseract is installed and its directory is in your system's PATH environment variable.")
                 return None
            except Exception as e_ocr:
                 print(f"Error during OCR on page {i+1}: {e_ocr}")
                 text += f"[OCR Error on page {i+1}]\n"
    except Exception as e:
        if "PDFInfoNotInstalledError" in str(e) or "pdfinfo" in str(e).lower():
             print(f"Error converting PDF: Poppler tools (like pdfinfo) not found or not in PATH.")
             print("Please install Poppler and ensure its 'bin' directory is in your PATH.")
        elif "No pages found" in str(e):
             print(f"Error converting PDF: pdf2image couldn't find pages in {pdf_path}. Is it a valid PDF?")
        else:
            print(f"Error converting PDF to images or during OCR processing for {pdf_path}: {e}")
        return None
    return text

def extract_text_unstructured(pdf_path, strategy="fast"):
    """Extracts text using the unstructured library."""
    if not UNSTRUCTURED_AVAILABLE:
        print("Unstructured method skipped: library not available.")
        return None
    text = ""
    try:
        print(f"Running unstructured with strategy='{strategy}'...")
        elements = partition_pdf(
             filename=pdf_path,
             strategy=strategy,
             infer_table_structure=True,
             )
        text = "\n\n".join([str(el) for el in elements])
    except ImportError as e:
         print(f"ImportError with unstructured (check dependencies for strategy '{strategy}'): {e}")
         return None
    except Exception as e:
        print(f"Error processing {pdf_path} with unstructured (strategy={strategy}): {e}")
        if strategy == "hi_res" and ("detectron2" in str(e) or "layoutparser" in str(e)):
            print("Hint: The 'hi_res' strategy requires Detectron2 and LayoutParser. Install with: pip install 'unstructured[local-inference]'")
        elif strategy == "ocr_only" and "pytesseract" in str(e):
             print("Hint: The 'ocr_only' strategy requires pytesseract and Tesseract OCR.")
        return None
    return text

def extract_markdown_pymupdf4llm(pdf_path):
    """Extracts Markdown using the pymupdf4llm library."""
    if not PYMUPDF4LLM_AVAILABLE:
        print("pymupdf4llm method skipped: library not available.")
        return None
    print("Running pymupdf4llm extraction...")
    try:
        markdown_output = pymupdf4llm_to_markdown(pdf_path)
        return markdown_output
    except Exception as e:
        print(f"Error processing {pdf_path} with pymupdf4llm: {e}")
        import traceback
        traceback.print_exc()
        return None

def extract_text_pypdf_visitor(pdf_path):
    """Extracts text using pypdf's visitor pattern for potentially more control."""
    extracted_data = {"text": ""}
    def visitor_body(text, cm, tm, fontDict, fontSize):
        if text and text.strip():
             extracted_data["text"] += text + " "
    print("Running pypdf visitor pattern extraction...")
    try:
        reader = pypdf.PdfReader(pdf_path)
        for i, page in enumerate(reader.pages):
             try:
                 page.extract_text(visitor_text=visitor_body)
                 extracted_data["text"] += "\n--- Page Break ---\n"
             except Exception as e_page:
                 print(f"Error processing page {i+1} with pypdf visitor: {e_page}")
                 extracted_data["text"] += f"\n[Error on Page {i+1}]\n"
        cleaned_text = re.sub(r'\s{2,}', ' ', extracted_data["text"])
        cleaned_text = re.sub(r'(\n\s*){2,}', '\n\n', cleaned_text).strip()
        return cleaned_text
    except pypdf.errors.PdfReadError as e_read:
        print(f"Error reading PDF {pdf_path} with pypdf: {e_read}")
        return None
    except Exception as e:
        print(f"Error processing {pdf_path} with pypdf visitor: {e}")
        import traceback
        traceback.print_exc()
        return None

# --- NEW: AlcheMark AI Extraction Function ---
def extract_markdown_alchemark(pdf_path, process_images=True, keep_images_inline=True):
    """
    Extracts structured Markdown using the AlcheMark AI library.
    Returns a single Markdown string concatenating text from all pages.
    """
    if not ALCHEMARK_AVAILABLE:
        print("AlcheMark AI method skipped: library not available.")
        return None

    print(f"Running AlcheMark AI extraction (process_images={process_images}, keep_images_inline={keep_images_inline})...")
    combined_markdown_parts = []
    try:
        # alchemark_results is a list of FormattedResult objects (or dict-like objects)
        alchemark_results = alchemark_pdf2md(
            pdf_path,
            process_images=process_images,
            keep_images_inline=keep_images_inline
        )

        if not alchemark_results:
            print(f"AlcheMark AI returned no results for {pdf_path}.")
            return "" # Return empty string for consistency (successful run, no content)

        for page_result in alchemark_results:
            # Accessing attributes as per AlcheMark documentation
            page_num = page_result.metadata.page
            page_text = page_result.text

            header = f"\n\n--- AlcheMark AI: Page {page_num} ---\n\n"
            combined_markdown_parts.append(header)
            combined_markdown_parts.append(page_text)

            # Optional: Log more details from AlcheMark's rich output
            # print(f"AlcheMark - Page {page_num}: {len(page_result.elements.tables)} tables, "
            #       f"{len(page_result.elements.images)} images, "
            #       f"{page_result.tokens} tokens, lang: {page_result.language}")

        return "".join(combined_markdown_parts).strip()

    except Exception as e:
        print(f"Error processing {pdf_path} with AlcheMark AI: {e}")
        import traceback
        traceback.print_exc()
        return None


# --- Main Pipeline Function ---

EXTRACTION_METHODS = {
    "pypdf": extract_text_pypdf,
    "pymupdf": extract_text_pymupdf,
    "pypdf_visitor": extract_text_pypdf_visitor,
    "ocr": extract_text_ocr,
    "unstructured_fast": lambda p: extract_text_unstructured(p, strategy="fast"),
    "unstructured_ocr": lambda p: extract_text_unstructured(p, strategy="ocr_only"),
    # "unstructured_hires": lambda p: extract_text_unstructured(p, strategy="hi_res"),
    "pymupdf4llm": extract_markdown_pymupdf4llm,
    "alchemark": lambda p: extract_markdown_alchemark(p, process_images=True, keep_images_inline=True),
}

# List of methods known to produce Markdown output
MARKDOWN_OUTPUT_METHODS = ["pymupdf4llm", "alchemark"]

def run_pdf_extraction_pipeline(pdf_path, methods_to_test, output_dir="pdf_extraction_results"):
    if not os.path.exists(pdf_path):
        print(f"Error: Input PDF not found at {pdf_path}")
        return None

    safe_pdf_name = re.sub(r'[\\/*?:"<>|]', '_', os.path.basename(pdf_path))
    base_filename = os.path.splitext(safe_pdf_name)[0]
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    method_output_dir = os.path.join(output_dir, f"{base_filename}_{timestamp}")

    if not os.path.exists(method_output_dir):
        try:
            os.makedirs(method_output_dir)
            print(f"Created output directory: {method_output_dir}")
        except OSError as e:
            print(f"Error creating output directory {method_output_dir}: {e}")
            method_output_dir = output_dir
            if not os.path.exists(method_output_dir):
                 try:
                     os.makedirs(method_output_dir)
                 except OSError as e_fallback:
                      print(f"Error creating fallback output directory {method_output_dir}: {e_fallback}")
                      return None

    results = {}
    print(f"\n--- Starting Extraction Pipeline for: {pdf_path} ---")
    print(f"--- Results will be saved in: {method_output_dir} ---")

    for method_name in methods_to_test:
        if method_name not in EXTRACTION_METHODS:
            print(f"Warning: Method '{method_name}' not recognized. Skipping.")
            continue

        # Availability checks
        if method_name == "ocr" and not PYTESSERACT_AVAILABLE:
             print(f"Skipping '{method_name}': Dependencies not met.")
             results[method_name] = {"output_file": None, "time_taken": 0, "success": False, "error": "Dependencies not met"}
             continue
        if method_name.startswith("unstructured") and not UNSTRUCTURED_AVAILABLE:
             print(f"Skipping '{method_name}': Dependency (unstructured) not met.")
             results[method_name] = {"output_file": None, "time_taken": 0, "success": False, "error": "Dependencies not met"}
             continue
        if method_name == "pymupdf4llm" and not PYMUPDF4LLM_AVAILABLE:
             print(f"Skipping '{method_name}': Dependency (pymupdf4llm) not met.")
             results[method_name] = {"output_file": None, "time_taken": 0, "success": False, "error": "Dependencies not met"}
             continue
        if method_name.startswith("alchemark") and not ALCHEMARK_AVAILABLE: # Check for AlcheMark
             print(f"Skipping '{method_name}': Dependency (alchemark-ai) not met.")
             results[method_name] = {"output_file": None, "time_taken": 0, "success": False, "error": "Dependencies not met"}
             continue

        print(f"\nRunning method: {method_name}...")
        start_time = time.time()
        output_content = None
        success = False
        error_message = ""

        try:
            extraction_func = EXTRACTION_METHODS[method_name]
            output_content = extraction_func(pdf_path)
            if output_content is not None:
                if isinstance(output_content, str) and output_content.strip():
                    success = True
                elif isinstance(output_content, str) and not output_content.strip():
                     success = True
                     print(f"Warning: Method '{method_name}' produced empty output.")
                else:
                     error_message = f"Extraction function for '{method_name}' returned non-string, non-None type: {type(output_content)}"
                     print(f"Warning: {error_message}")
                     output_content = str(output_content)
                     success = False
            else:
                 error_message = f"Extraction function for '{method_name}' returned None."
                 print(f"Info: {error_message}")
        except Exception as e:
            error_message = f"Unexpected error during '{method_name}' execution: {e}"
            print(error_message)
            import traceback
            traceback.print_exc()
            success = False

        end_time = time.time()
        time_taken = end_time - start_time
        file_extension = 'md' if method_name in MARKDOWN_OUTPUT_METHODS else 'txt'
        output_filename = f"{method_name}.{file_extension}"
        output_filepath = os.path.join(method_output_dir, output_filename)

        if success and output_content is not None:
             if not isinstance(output_content, str):
                 print(f"Internal Warning: Output for '{method_name}' was not string before write. Converting.")
                 output_content = str(output_content)
             try:
                with open(output_filepath, "w", encoding="utf-8") as f:
                    f.write(output_content)
                print(f"Success! Time taken: {time_taken:.2f} seconds. Output saved to: {output_filepath}")
             except Exception as e_write:
                 print(f"Error writing output file {output_filepath}: {e_write}")
                 success = False
                 error_message += f" | File write error: {e_write}"
                 output_filepath = None
        else:
             if not error_message:
                 error_message = f"Method '{method_name}' did not produce valid output or failed silently."
             print(f"Failed! Time taken: {time_taken:.2f} seconds. Error details logged above.")
             output_filepath = None

        results[method_name] = {
            "output_file": output_filepath,
            "time_taken": time_taken,
            "success": success,
            "error": error_message if not success else ""
        }

    print("\n--- Extraction Pipeline Finished ---")
    print("\nSummary:")
    for method in sorted(results.keys()):
        result = results[method]
        status = "Success" if result['success'] else "Failed"
        error_info = f" | Error: {result['error']}" if not result['success'] else ""
        file_info = f"| Output: {result['output_file']}" if result['output_file'] else "| No output file"
        print(f"- {method}: {status} ({result['time_taken']:.2f}s) {file_info} {error_info}")

    summary_filename = f"summary_{base_filename}_{timestamp}.json"
    summary_filepath = os.path.join(output_dir, summary_filename)
    try:
        with open(summary_filepath, 'w', encoding='utf-8') as f_summary:
            json.dump(results, f_summary, indent=4)
        print(f"\nSummary results saved to: {summary_filepath}")
    except Exception as e_json:
        print(f"\nError saving summary JSON file {summary_filepath}: {e_json}")

    return results

# --- Example Usage ---
if __name__ == "__main__":
    # --- Configuration ---
    # <--- CHANGE THIS to your PDF file path --->
    # pdf_file_to_process = "path/to/your/document.pdf" # General placeholder
    pdf_file_to_process = "/home/teip/PycharmProjects/MAT_NER/pdfs/1556-276X-5-217.pdf" # Specific example

    methods_to_run = [
        "pypdf",
        "pymupdf",
        "pypdf_visitor",
        "ocr",
        # "unstructured_fast",
        # "unstructured_ocr",
        # "unstructured_hires",
        "pymupdf4llm",
        "alchemark",      # Added AlcheMark AI
    ]

    if not os.path.exists(pdf_file_to_process):
         print(f"Error: The example PDF file was not found at '{pdf_file_to_process}'")
         print("Please update the 'pdf_file_to_process' variable in the script to point to a valid PDF file.")
    elif not pdf_file_to_process.lower().endswith(".pdf"):
         print(f"Error: The specified file '{pdf_file_to_process}' does not appear to be a PDF.")
    else:
        output_directory = "pdf_extraction_output_with_alchemark" # Updated directory name

        extraction_results = run_pdf_extraction_pipeline(
            pdf_path=pdf_file_to_process,
            methods_to_test=methods_to_run,
            output_dir=output_directory
        )

        if extraction_results:
            print(f"\nPlease review the output files and the summary JSON in the '{output_directory}' directory.")
        else:
            print("\nPipeline execution did not complete successfully.")