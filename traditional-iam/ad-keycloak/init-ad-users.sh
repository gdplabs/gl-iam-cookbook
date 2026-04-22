#!/bin/bash
# Seeds the Active Directory domain with demo users and groups.
# Runs as a one-shot sidecar; idempotent (skips users/groups that already exist).

set -e

DC_HOST="ldap://samba-ad:389"
ADMIN_AUTH="Administrator%Password123!"

create_user() {
  local username="$1"
  local password="$2"
  local given="$3"
  local surname="$4"
  local mail="$5"

  if samba-tool user show "$username" -U "$ADMIN_AUTH" -H "$DC_HOST" >/dev/null 2>&1; then
    echo "User '$username' already exists — skipping."
  else
    samba-tool user create "$username" "$password" \
      --given-name="$given" --surname="$surname" --mail-address="$mail" \
      -U "$ADMIN_AUTH" -H "$DC_HOST"
  fi
}

create_group() {
  local group="$1"
  if samba-tool group show "$group" -U "$ADMIN_AUTH" -H "$DC_HOST" >/dev/null 2>&1; then
    echo "Group '$group' already exists — skipping."
  else
    samba-tool group add "$group" -U "$ADMIN_AUTH" -H "$DC_HOST"
  fi
}

add_member() {
  local group="$1"
  local member="$2"
  # Check membership first to keep re-runs quiet.
  if samba-tool group listmembers "$group" -U "$ADMIN_AUTH" -H "$DC_HOST" 2>/dev/null \
     | grep -qx "$member"; then
    echo "'$member' already in '$group' — skipping."
  else
    samba-tool group addmembers "$group" "$member" -U "$ADMIN_AUTH" -H "$DC_HOST"
  fi
}

echo "Seeding AD domain example.org…"

create_user jdoe   jdoe123   John  Doe   jdoe@example.org
create_user asmith asmith123 Alice Smith asmith@example.org

create_group members
create_group admins

add_member members jdoe
add_member members asmith
add_member admins  asmith

echo "Seeding complete."
samba-tool user list -U "$ADMIN_AUTH" -H "$DC_HOST"
