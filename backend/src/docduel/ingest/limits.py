MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_PAGES = 3
MAX_CSV_ROWS = 200
# A PDF page with fewer meaningful (alphanumeric) characters than this is treated as a scan.
MIN_TEXT_CHARS_PER_PAGE = 30
# Azure Document Intelligence free tier (F0) accepts files up to 4 MB.
AZURE_MAX_IMAGE_BYTES = 4 * 1024 * 1024
