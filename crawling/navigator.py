from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def go_to_dashboard(driver):
    """Navigates to the ISIS dashboard after login (if not already there)."""
    driver.get("https://isis.tu-berlin.de/my/courses.php")
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, "coursebox"))
    )

def open_course_by_id(driver, course_id: str):
    """
    Opens a course by its ISIS course ID.
    This ID comes from the URL like: https://isis.tu-berlin.de/course/view.php?id=XXXXX
    """
    course_url = f"https://isis.tu-berlin.de/course/view.php?id={course_id}"
    driver.get(course_url)

    # Optional: wait for course page to load
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "page-header"))
    )

def open_course_by_name(driver, course_name: str):
    """
    Searches the dashboard for a course tile containing the course name.
    Use this only if you don't have the course ID.
    """
    go_to_dashboard(driver)
    WebDriverWait(driver, 10).until(
        EC.presence_of_all_elements_located((By.CLASS_NAME, "coursebox"))
    )
    course_boxes = driver.find_elements(By.CLASS_NAME, "coursebox")

    for box in course_boxes:
        if course_name.lower() in box.text.lower():
            link = box.find_element(By.TAG_NAME, "a")
            link.click()
            return

    raise Exception(f"Course '{course_name}' not found on the dashboard.")

