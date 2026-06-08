#!/usr/bin/env python3
import argparse
import getpass
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from labmon.auth import hash_password, load_users, write_users  # noqa: E402
from labmon.config import PROJECT_ROOT  # noqa: E402


def users_file_from_args(args):
    return args.users_file or os.getenv("LABMON_USERS_FILE") or str(PROJECT_ROOT / "labmon-users.json")


def add_user(args):
    username = args.username.strip()
    if not username:
        raise SystemExit("username cannot be empty")
    password = args.password or getpass.getpass("password: ")
    if not password:
        raise SystemExit("password cannot be empty")
    users_file = users_file_from_args(args)
    users = load_users(users_file)
    users[username] = hash_password(password)
    write_users(users_file, users)
    print("added {}".format(username))
    print("users file {}".format(users_file))


def remove_user(args):
    users_file = users_file_from_args(args)
    users = load_users(users_file)
    if args.username not in users:
        raise SystemExit("{} not found".format(args.username))
    users.pop(args.username)
    write_users(users_file, users)
    print("removed {}".format(args.username))


def list_users(args):
    users = load_users(users_file_from_args(args))
    for username in sorted(users):
        print(username)


def main():
    parser = argparse.ArgumentParser(description="Manage LabMon local users")
    parser.add_argument("--users-file", help="Path to LabMon users JSON file")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Add or replace a user")
    add_parser.add_argument("username")
    add_parser.add_argument("--password", help="Password value. Omit to prompt securely.")
    add_parser.set_defaults(func=add_user)

    remove_parser = subparsers.add_parser("remove", help="Remove a user")
    remove_parser.add_argument("username")
    remove_parser.set_defaults(func=remove_user)

    list_parser = subparsers.add_parser("list", help="List users")
    list_parser.set_defaults(func=list_users)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
