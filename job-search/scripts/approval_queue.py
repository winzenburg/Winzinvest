#!/usr/bin/env python3
"""
Approval Queue
Interactive CLI for reviewing and approving outreach messages.

Workflow:
1. Load pending messages
2. Display each message
3. User approves/edits/rejects
4. Move approved messages to ready-to-send queue
"""

import json
from pathlib import Path
from typing import List, Dict
import sys

# Project paths
PROJECT_DIR = Path(__file__).parent.parent
DATA_DIR = PROJECT_DIR / "data"
OUTREACH_DIR = DATA_DIR / "outreach"
PENDING_DIR = OUTREACH_DIR / "pending"
APPROVED_DIR = OUTREACH_DIR / "approved"
REJECTED_DIR = OUTREACH_DIR / "rejected"

# Create directories
APPROVED_DIR.mkdir(parents=True, exist_ok=True)
REJECTED_DIR.mkdir(parents=True, exist_ok=True)


def load_pending_messages() -> List[Dict]:
    """Load all pending outreach messages."""
    messages = []
    
    for filepath in PENDING_DIR.glob("*.json"):
        with open(filepath) as f:
            msg = json.load(f)
            msg['_filepath'] = filepath
            messages.append(msg)
    
    # Sort by company name
    messages.sort(key=lambda x: (x.get('company_name', ''), x.get('contact_title', '')))
    
    return messages


def display_message(msg: Dict, index: int, total: int):
    """Display message for review."""
    print("\n" + "=" * 80)
    print(f"Message {index + 1} of {total}")
    print("=" * 80)
    print(f"\n📧 TO: {msg.get('contact_name', 'Unknown')}")
    print(f"   Title: {msg.get('contact_title', 'Unknown')}")
    print(f"   Company: {msg.get('company_name', 'Unknown')}")
    print(f"   Channel: {msg.get('channel', 'linkedin').upper()}")
    print(f"\n{'-' * 80}")
    print(msg.get('message', ''))
    print(f"{'-' * 80}\n")
    
    # Show personalization details
    pers = msg.get('personalization', {})
    print(f"📌 Personalization:")
    print(f"   Hook: {pers.get('hook', 'N/A')}")
    print(f"   Angle: {pers.get('angle', 'N/A')}")
    print()


def get_user_action() -> str:
    """Prompt user for action."""
    print("Actions:")
    print("  [a] Approve (move to ready-to-send)")
    print("  [e] Edit message")
    print("  [r] Reject (skip this contact)")
    print("  [s] Skip for now (leave in pending)")
    print("  [q] Quit")
    
    while True:
        choice = input("\nYour choice: ").strip().lower()
        if choice in ['a', 'e', 'r', 's', 'q']:
            return choice
        print("Invalid choice. Please enter a, e, r, s, or q.")


def edit_message(msg: Dict) -> Dict:
    """Allow user to edit the message."""
    print("\n📝 Edit mode")
    print("Paste your edited message below. Press Ctrl+D (Mac/Linux) or Ctrl+Z (Windows) when done.\n")
    
    try:
        lines = []
        while True:
            try:
                line = input()
                lines.append(line)
            except EOFError:
                break
        
        edited_message = '\n'.join(lines)
        
        if edited_message.strip():
            msg['message'] = edited_message
            msg['edited'] = True
            print("\n✅ Message updated")
        else:
            print("\n⚠️  No changes made (empty input)")
        
    except KeyboardInterrupt:
        print("\n⚠️  Edit cancelled")
    
    return msg


def approve_message(msg: Dict):
    """Move message to approved queue."""
    filepath = msg['_filepath']
    approved_path = APPROVED_DIR / filepath.name
    
    # Update status
    msg['status'] = 'approved'
    del msg['_filepath']  # Remove internal field
    
    # Save to approved
    with open(approved_path, 'w') as f:
        json.dump(msg, f, indent=2)
    
    # Remove from pending
    filepath.unlink()
    
    print(f"✅ Approved: {msg['company_name']} - {msg['contact_title']}")


def reject_message(msg: Dict):
    """Move message to rejected queue."""
    filepath = msg['_filepath']
    rejected_path = REJECTED_DIR / filepath.name
    
    # Update status
    msg['status'] = 'rejected'
    del msg['_filepath']
    
    # Save to rejected
    with open(rejected_path, 'w') as f:
        json.dump(msg, f, indent=2)
    
    # Remove from pending
    filepath.unlink()
    
    print(f"❌ Rejected: {msg['company_name']} - {msg['contact_title']}")


def main():
    """Run approval queue CLI."""
    print("\n" + "=" * 80)
    print("OUTREACH APPROVAL QUEUE")
    print("=" * 80)
    
    # Load pending messages
    messages = load_pending_messages()
    
    if not messages:
        print("\n✅ No pending messages to review!")
        print("   Generate new messages with: python3 scripts/generate_outreach.py")
        return
    
    print(f"\n📊 Pending messages: {len(messages)}")
    print("\nReview each message and choose: Approve, Edit, Reject, or Skip")
    
    approved_count = 0
    rejected_count = 0
    
    for i, msg in enumerate(messages):
        display_message(msg, i, len(messages))
        
        action = get_user_action()
        
        if action == 'a':
            approve_message(msg)
            approved_count += 1
        
        elif action == 'e':
            msg = edit_message(msg)
            # Ask again after editing
            print("\nApprove edited message?")
            confirm = get_user_action()
            if confirm == 'a':
                approve_message(msg)
                approved_count += 1
        
        elif action == 'r':
            reject_message(msg)
            rejected_count += 1
        
        elif action == 's':
            print(f"⏭️  Skipped: {msg['company_name']} - {msg['contact_title']}")
        
        elif action == 'q':
            print("\n👋 Exiting approval queue")
            break
    
    # Summary
    print("\n" + "=" * 80)
    print("APPROVAL SUMMARY")
    print("=" * 80)
    print(f"✅ Approved: {approved_count}")
    print(f"❌ Rejected: {rejected_count}")
    print(f"⏭️  Skipped: {len(load_pending_messages())}")
    print("\n" + "=" * 80)
    
    if approved_count > 0:
        print(f"\n📋 Next: Send approved messages manually via LinkedIn")
        print(f"   Approved messages are in: {APPROVED_DIR}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Approval queue cancelled")
        sys.exit(0)
