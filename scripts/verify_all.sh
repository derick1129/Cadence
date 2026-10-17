#!/usr/bin/env bash
set -uo pipefail

# scripts/verify_all.sh
# Runs all verification checks sequentially and prints a summary.
# Exits with 0 if all checks pass, 1 if any check fails.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Auto-activate local Python virtual environment if present and not already active
if [ -z "${VIRTUAL_ENV:-}" ]; then
  if [ -f "$REPO_ROOT/.venv/bin/activate" ]; then
    # shellcheck source=/dev/null
    source "$REPO_ROOT/.venv/bin/activate"
  elif [ -f "$REPO_ROOT/venv/bin/activate" ]; then
    # shellcheck source=/dev/null
    source "$REPO_ROOT/venv/bin/activate"
  fi
fi

declare -a CHECK_NAMES
declare -a CHECK_STATUSES
FAILED=0

run_check() {
  local name="$1"
  local cmd="$2"

  echo ""
  echo "================================================================"
  echo " Running check: $name"
  echo " Command: $cmd"
  echo "================================================================"

  if eval "$cmd"; then
    echo ">>> [PASS] $name"
    CHECK_NAMES+=("$name")
    CHECK_STATUSES+=("PASS")
  else
    echo ">>> [FAIL] $name"
    CHECK_NAMES+=("$name")
    CHECK_STATUSES+=("FAIL")
    FAILED=1
  fi
}

echo "================================================================"
echo " Starting Cadence Verification Suite"
echo " Working directory: $REPO_ROOT"
echo "================================================================"

# 1. Backend Lint
run_check "Backend lint" "ruff check . && ruff format --check ."

# 2. Backend Types
if [ -d "worker" ] && find worker -name "*.py" 2>/dev/null | grep -q .; then
  run_check "Backend types" "mypy backend worker"
else
  run_check "Backend types" "mypy backend"
fi

# 3. Backend Tests
run_check "Backend tests" "pytest -q"

# 4. Boundary Enforcement
run_check "Boundaries" "lint-imports"

# 5. Frontend Lint
run_check "Frontend lint" "(cd frontend && pnpm lint)"

# 6. Frontend Types
run_check "Frontend types" "(cd frontend && pnpm typecheck)"

# 7. Frontend Tests
run_check "Frontend tests" "(cd frontend && pnpm test)"

echo ""
echo "================================================================"
echo " Verification Summary"
echo "================================================================"
for i in "${!CHECK_NAMES[@]}"; do
  printf "  [%s] %s\n" "${CHECK_STATUSES[$i]}" "${CHECK_NAMES[$i]}"
done
echo "================================================================"

if [ "$FAILED" -ne 0 ]; then
  echo "Verification FAILED: One or more checks failed."
  exit 1
else
  echo "Verification PASSED: All checks passed successfully."
  exit 0
fi
