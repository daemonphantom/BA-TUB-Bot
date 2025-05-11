from urllib.parse import urlparse, parse_qs
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
loggerwire = logging.getLogger('seleniumwire')
loggerwire.setLevel(logging.ERROR)

def get_logger(module_name: str):
    return logging.getLogger(module_name)



def get_course_id_from_url(url):
    """
    Extract the course id from a course URL.
    Assumes the URL includes a query parameter such as ?id=12345.
    """
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)
    return query_params.get("id", ["unknown"])[0]