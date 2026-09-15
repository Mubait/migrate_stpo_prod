from migrate_cities import migrate_cities
from migrate_divisions import migrate_divisions

RESET = "\033[0m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"

def main():
    migrate_cities()
    migrate_divisions()

if __name__ == "__main__":
    main()
