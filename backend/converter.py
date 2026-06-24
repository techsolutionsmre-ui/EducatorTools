import logging
import os
import sys
import subprocess
from pdf2docx import Converter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Converter")

def convert_pdf_to_docx(pdf_path: str, docx_path: str) -> int:
    """
    Converts a local PDF file into a Microsoft Word (.docx) document.
    
    1. If running on Windows, attempts to use Word COM automation via PowerShell.
       This provides 100% layout and text accuracy (handling complex tables, fonts, etc.).
    2. If Word COM is not available or we are running on Linux (e.g. Docker/OCI),
       it falls back to pdf2docx, running on a single thread to limit CPU spikes.
       
    Returns the page count of the converted document.
    """
    # Normalize paths with forward slashes for PowerShell compatibility
    abs_pdf = os.path.abspath(pdf_path).replace("\\", "/")
    abs_docx = os.path.abspath(docx_path).replace("\\", "/")

    if sys.platform == "win32":
        try:
            logger.info("Windows detected. Attempting to use Microsoft Word COM via PowerShell...")
            
            # Inline PowerShell script
            # 16 = wdFormatXMLDocument (docx)
            # 2 = wdStatisticPages (page count)
            ps_script = f"""
            try {{
                # Bypass warning prompt
                $versions = @("15.0", "16.0")
                foreach ($v in $versions) {{
                    $regPath = "HKCU:\\Software\\Microsoft\\Office\\$v\\Word\\Options"
                    if (!(Test-Path $regPath)) {{
                        New-Item -Path $regPath -Force | Out-Null
                    }}
                    New-ItemProperty -Path $regPath -Name "DisableConvertPdfWarning" -Value 1 -PropertyType DWORD -Force | Out-Null
                }}

                $word = New-Object -ComObject Word.Application
                $word.Visible = $false
                $word.DisplayAlerts = 0
                
                $doc = $word.Documents.Open("{abs_pdf}", $false, $true)
                $doc.SaveAs2("{abs_docx}", 16)
                $pageCount = $doc.ComputeStatistics(2)
                $doc.Close()
                $word.Quit()
                Write-Output "SUCCESS_PAGES:$pageCount"
            }} catch {{
                Write-Error $_
                if ($word) {{ $word.Quit() }}
                exit 1
            }}
            """
            
            result = subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0 and "SUCCESS_PAGES:" in result.stdout:
                # Find the page count in stdout
                for line in result.stdout.split("\n"):
                    if "SUCCESS_PAGES:" in line:
                        page_count = int(line.split("SUCCESS_PAGES:")[1].strip())
                        logger.info(f"Word COM conversion successful! Pages: {page_count}")
                        return page_count
            else:
                logger.warning(f"Word COM conversion script failed. Stdout: {result.stdout}, Stderr: {result.stderr}")
                
        except Exception as win_err:
            logger.error(f"Failed to execute Word COM conversion: {str(win_err)}")
            
        logger.info("Falling back to local pdf2docx engine...")

    # Fallback / Linux Engine: pdf2docx
    cv = None
    try:
        cv = Converter(pdf_path)
        page_count = len(cv.pages)
        
        # Run conversion sequentially to protect CPU resources
        cv.convert(docx_path, start=0, end=None, multiprocessing=False)
        return page_count
    except Exception as e:
        logger.error(f"pdf2docx fallback conversion failed: {str(e)}")
        raise e
    finally:
        if cv:
            cv.close()
