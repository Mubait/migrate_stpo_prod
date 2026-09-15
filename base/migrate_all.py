from migrate_users import migrate_users

RESET = "\033[0m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"

def main():
    migrate_users()

if __name__ == "__main__":
    main()
