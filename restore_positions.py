"""positions.json 백업 목록/복원 CLI

position_tracker._save() 는 매 저장마다 etc/positions_backups/ 로 회전 백업
(최신 5개)을 남긴다. 이 CLI 는 백업 목록을 보거나 특정 백업을 복원하는
편의 도구다.

Usage:
    python restore_positions.py --list
    python restore_positions.py --restore 0     # 0 = 최신, 1 = 그 이전 ...

이 스크립트는 KIS API 를 호출하지 않으며, 로컬 파일만 다룬다.
"""
import argparse
import sys

import position_tracker


def cmd_list() -> int:
    backups = position_tracker.list_backups()
    if not backups:
        print(f"백업 없음 ({position_tracker.BACKUP_DIR}/ 비어있거나 미존재)")
        return 0
    print(f"백업 디렉토리: {position_tracker.BACKUP_DIR}")
    print(f"총 {len(backups)}개 (최신 순)\n")
    print(f"{'idx':>4}  {'filename':<44}  {'mtime':<20}  {'count':>5}  {'size':>7}  valid")
    print("-" * 96)
    for b in backups:
        marker = "✓" if b["valid"] else "✗"
        print(
            f"{b['index']:>4}  {b['filename']:<44}  {b['mtime']:<20}  "
            f"{b['position_count']:>5}  {b['size']:>7}  {marker}"
        )
    return 0


def cmd_restore(index: int) -> int:
    ok = position_tracker.restore_backup(index)
    if ok:
        print(f"✓ 백업 #{index} 로 {position_tracker.POSITION_FILE} 복원 완료")
        return 0
    print(
        f"✗ 백업 #{index} 복원 실패 — 인덱스 범위 초과 또는 백업이 손상되었을 수 있습니다. "
        f"`--list` 로 확인하세요.",
        file=sys.stderr,
    )
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="positions.json 백업 관리 (목록 표시 / 복원)",
    )
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--list", action="store_true", help="백업 목록 표시")
    group.add_argument(
        "--restore",
        type=int,
        metavar="IDX",
        help="백업 #IDX 로 복원 (0=최신, --list 로 인덱스 확인)",
    )
    args = parser.parse_args()

    if args.list:
        return cmd_list()
    if args.restore is not None:
        return cmd_restore(args.restore)

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
