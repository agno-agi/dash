"""
Generate SaaS Metrics Data
==========================

Creates a synthetic SaaS dataset for a fictional B2B company ("Acme Analytics")
with ~2 years of data (Jan 2024 — Dec 2025). Generates realistic patterns:
growth curves, seasonal churn, usage-correlated retention.

Usage:
    python scripts/generate_data.py              # Generate and load
    python scripts/generate_data.py --seed 42    # Reproducible
    python scripts/generate_data.py --drop       # Drop and recreate tables
"""

import argparse
import random
from datetime import date, datetime, timedelta
from typing import NamedTuple

import pandas as pd
from sqlalchemy import create_engine, text

from db import db_url


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
class PlanInfo(NamedTuple):
    base_mrr: int
    seats: tuple[int, int]


PLANS: dict[str, PlanInfo] = {
    "starter": PlanInfo(base_mrr=29, seats=(1, 3)),
    "professional": PlanInfo(base_mrr=79, seats=(3, 10)),
    "business": PlanInfo(base_mrr=199, seats=(10, 50)),
    "enterprise": PlanInfo(base_mrr=499, seats=(50, 200)),
}

INDUSTRIES = ["technology", "healthcare", "finance", "retail", "education"]
COMPANY_SIZES = ["startup", "smb", "mid_market", "enterprise"]
COUNTRIES = ["US", "US", "US", "UK", "UK", "DE", "CA", "AU", "FR", "IN"]  # weighted US
SOURCES = ["organic", "referral", "paid", "partner"]
TICKET_CATEGORIES = ["billing", "technical", "feature_request", "onboarding"]
TICKET_PRIORITIES = ["low", "medium", "medium", "high", "critical"]  # weighted medium
CANCELLATION_REASONS = [
    "too_expensive",
    "switched_competitor",
    "no_longer_needed",
    "missing_features",
    "poor_support",
    "budget_cuts",
]

# Company name parts for realistic generation
PREFIXES = [
    "Apex",
    "Bright",
    "Cloud",
    "Data",
    "Edge",
    "Flow",
    "Grid",
    "Hub",
    "Iris",
    "Jet",
    "Kite",
    "Loom",
    "Meta",
    "Nova",
    "Orbit",
    "Pulse",
    "Quark",
    "Rise",
    "Sync",
    "Trace",
    "Unity",
    "Vibe",
    "Wave",
    "Xenon",
    "Yield",
    "Zen",
    "Atlas",
    "Beacon",
    "Craft",
    "Drift",
]
SUFFIXES = [
    "Labs",
    "AI",
    "Tech",
    "Systems",
    "IO",
    "HQ",
    "Works",
    "Co",
    "Analytics",
    "Cloud",
    "Digital",
    "Solutions",
    "Group",
    "Inc",
    "Software",
    "Dynamics",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _company_name(rng: random.Random, used: set[str]) -> str:
    for _ in range(100):
        name = f"{rng.choice(PREFIXES)}{rng.choice(SUFFIXES)}"
        if name not in used:
            used.add(name)
            return name
    return f"Company{len(used)}"


def _plan_for_size(rng: random.Random, size: str) -> str:
    weights = {
        "startup": [0.6, 0.3, 0.08, 0.02],
        "smb": [0.2, 0.5, 0.25, 0.05],
        "mid_market": [0.05, 0.2, 0.5, 0.25],
        "enterprise": [0.02, 0.05, 0.25, 0.68],
    }
    plans = list(PLANS.keys())
    return rng.choices(plans, weights=weights[size])[0]


def _churn_probability(plan: str, usage_ratio: float) -> float:
    """Monthly churn probability — lower for enterprise, higher for low usage."""
    base = {"starter": 0.08, "professional": 0.05, "business": 0.03, "enterprise": 0.015}
    p = base[plan]
    # Low usage multiplier (usage_ratio < 0.3 → 2x churn)
    if usage_ratio < 0.3:
        p *= 2.0
    elif usage_ratio < 0.5:
        p *= 1.3
    return min(p, 0.25)


def _random_date_in_month(rng: random.Random, year: int, month: int) -> date:
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    delta = (end - start).days
    return start + timedelta(days=rng.randint(0, delta - 1))


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------
def generate(seed: int = 42) -> dict[str, pd.DataFrame]:
    """Generate all SaaS metrics tables. Returns dict of DataFrames."""
    rng = random.Random(seed)

    customers: list[dict] = []
    subscriptions: list[dict] = []
    plan_changes: list[dict] = []
    invoices: list[dict] = []
    usage_metrics: list[dict] = []
    support_tickets: list[dict] = []

    used_names: set[str] = set()
    cust_id = 0
    sub_id = 0
    invoice_id = 0
    ticket_id = 0

    # Monthly new customer counts (growth curve)
    monthly_new = [
        15,
        18,
        20,
        22,
        25,
        28,
        22,
        30,
        35,
        32,
        28,
        40,  # 2024
        38,
        42,
        45,
        40,
        48,
        50,
        45,
        52,
        55,
        50,
        48,
        60,  # 2025
    ]

    # Track active subscriptions for churn simulation
    active_subs: dict[int, dict] = {}  # cust_id → sub info

    for month_offset, new_count in enumerate(monthly_new):
        year = 2024 + month_offset // 12
        month = (month_offset % 12) + 1
        month_start = date(year, month, 1)
        if month == 12:
            month_end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(year, month + 1, 1) - timedelta(days=1)

        # --- New customers this month ---
        for _ in range(new_count):
            cust_id += 1
            size = rng.choices(COMPANY_SIZES, weights=[0.35, 0.30, 0.20, 0.15])[0]
            plan = _plan_for_size(rng, size)
            signup = _random_date_in_month(rng, year, month)

            # 10% of new customers start as trial
            is_trial = rng.random() < 0.10
            customers.append(
                {
                    "id": cust_id,
                    "company_name": _company_name(rng, used_names),
                    "industry": rng.choice(INDUSTRIES),
                    "company_size": size,
                    "country": rng.choice(COUNTRIES),
                    "signup_date": signup,
                    "source": rng.choice(SOURCES),
                    "status": "trial" if is_trial else "active",
                }
            )

            plan_info = PLANS[plan]
            seats = rng.randint(*plan_info.seats)
            base_mrr = plan_info.base_mrr * max(1, seats // plan_info.seats[0])
            # Add some variance
            mrr = round(base_mrr * rng.uniform(0.9, 1.1), 2)

            sub_id += 1
            billing = rng.choices(["monthly", "annual"], weights=[0.65, 0.35])[0]
            subscriptions.append(
                {
                    "id": sub_id,
                    "customer_id": cust_id,
                    "plan": plan,
                    "mrr": mrr,
                    "seats": seats,
                    "billing_cycle": billing,
                    "started_at": datetime.combine(signup, datetime.min.time()),
                    "ended_at": None,
                    "status": "active",
                    "cancellation_reason": None,
                }
            )

            active_subs[cust_id] = {
                "sub_id": sub_id,
                "plan": plan,
                "mrr": mrr,
                "seats": seats,
                "billing_cycle": billing,
                "signup": signup,
            }

        # --- Process active customers this month ---
        churned_this_month = []
        for cid, info in list(active_subs.items()):
            # Skip customers who signed up this month (grace period)
            if info["signup"] >= month_start:
                continue

            # Usage generation
            plan_info = PLANS[info["plan"]]
            base_calls = {"starter": 500, "professional": 2000, "business": 8000, "enterprise": 25000}
            usage_ratio = rng.uniform(0.1, 1.0)
            # Enterprise tends to use more
            if info["plan"] == "enterprise":
                usage_ratio = rng.uniform(0.4, 1.0)

            api_calls = int(base_calls[info["plan"]] * usage_ratio * rng.uniform(0.8, 1.2))
            active_users = max(1, int(info["seats"] * usage_ratio * rng.uniform(0.5, 1.0)))
            storage = round(info["seats"] * rng.uniform(50, 500), 2)
            reports = int(active_users * rng.uniform(1, 10))

            # Sample 3-5 days per month for usage metrics
            for _ in range(rng.randint(3, 5)):
                usage_day = _random_date_in_month(rng, year, month)
                usage_metrics.append(
                    {
                        "customer_id": cid,
                        "metric_date": usage_day,
                        "api_calls": int(api_calls * rng.uniform(0.7, 1.3) / 5),
                        "active_users": max(1, active_users + rng.randint(-2, 2)),
                        "storage_mb": round(storage * rng.uniform(0.95, 1.05), 2),
                        "reports_generated": max(0, reports + rng.randint(-3, 3)),
                        "integrations_active": rng.randint(1, min(8, info["seats"])),
                    }
                )

            # Invoice generation (monthly billing or annual renewal month)
            billing = info["billing_cycle"]
            generate_invoice = billing == "monthly" or (billing == "annual" and month == info["signup"].month)
            if generate_invoice:
                invoice_id += 1
                amount = info["mrr"] if billing == "monthly" else info["mrr"] * 12 * 0.9  # 10% annual discount
                issued = _random_date_in_month(rng, year, month)
                roll = rng.random()
                if roll < 0.03:
                    inv_status = "failed"
                elif roll < 0.05:
                    inv_status = "pending"
                elif roll < 0.06:
                    inv_status = "refunded"
                else:
                    inv_status = "paid"
                paid_ok = inv_status == "paid"
                invoices.append(
                    {
                        "id": invoice_id,
                        "customer_id": cid,
                        "subscription_id": info["sub_id"],
                        "amount": round(amount, 2),
                        "currency": "USD",
                        "status": inv_status,
                        "issued_at": datetime.combine(issued, datetime.min.time()),
                        "paid_at": datetime.combine(issued + timedelta(days=rng.randint(0, 5)), datetime.min.time())
                        if paid_ok
                        else None,
                        "period_start": month_start,
                        "period_end": month_end,
                    }
                )

            # Support tickets (more tickets for lower plans / lower usage)
            ticket_prob = {"starter": 0.15, "professional": 0.10, "business": 0.08, "enterprise": 0.12}
            if rng.random() < ticket_prob[info["plan"]]:
                ticket_id += 1
                created = _random_date_in_month(rng, year, month)
                resolved = rng.random() > 0.15  # 85% resolution rate
                resolve_days = rng.randint(0, 7) if resolved else None
                # Resolved tickets: 70% closed, 30% resolved (closed = confirmed by customer)
                if resolved:
                    ticket_status = "closed" if rng.random() < 0.7 else "resolved"
                else:
                    ticket_status = rng.choice(["open", "in_progress"])
                support_tickets.append(
                    {
                        "id": ticket_id,
                        "customer_id": cid,
                        "priority": rng.choice(TICKET_PRIORITIES),
                        "category": rng.choice(TICKET_CATEGORIES),
                        "status": ticket_status,
                        "created_at": datetime.combine(created, datetime.min.time()),
                        "resolved_at": datetime.combine(created + timedelta(days=resolve_days), datetime.min.time())
                        if resolve_days is not None
                        else None,
                        "satisfaction_score": rng.randint(1, 5) if resolved and rng.random() > 0.3 else None,
                    }
                )

            # Churn check
            churn_p = _churn_probability(info["plan"], usage_ratio)
            # January churn spike
            if month == 1:
                churn_p *= 1.5

            if rng.random() < churn_p:
                churn_date = _random_date_in_month(rng, year, month)
                # Update subscription
                for s in subscriptions:
                    if s["id"] == info["sub_id"]:
                        s["ended_at"] = datetime.combine(churn_date, datetime.min.time())
                        s["status"] = "cancelled"
                        s["cancellation_reason"] = rng.choice(CANCELLATION_REASONS)
                        break
                # Update customer
                for c in customers:
                    if c["id"] == cid:
                        c["status"] = "churned"
                        break
                # Plan change record
                plan_changes.append(
                    {
                        "customer_id": cid,
                        "previous_plan": info["plan"],
                        "new_plan": None,
                        "previous_mrr": info["mrr"],
                        "new_mrr": 0,
                        "change_type": "cancellation",
                        "changed_at": datetime.combine(churn_date, datetime.min.time()),
                    }
                )
                churned_this_month.append(cid)
                continue

            # Upgrade/downgrade check (2% monthly)
            if rng.random() < 0.02:
                plans_list = list(PLANS.keys())
                current_idx = plans_list.index(info["plan"])
                # Upgrades more likely than downgrades
                if rng.random() < 0.7 and current_idx < len(plans_list) - 1:
                    new_plan = plans_list[current_idx + 1]
                    change_type = "upgrade"
                elif current_idx > 0:
                    new_plan = plans_list[current_idx - 1]
                    change_type = "downgrade"
                else:
                    continue

                new_plan_info = PLANS[new_plan]
                new_seats = rng.randint(*new_plan_info.seats)
                new_mrr = round(
                    new_plan_info.base_mrr * max(1, new_seats // new_plan_info.seats[0]) * rng.uniform(0.9, 1.1),
                    2,
                )
                change_date = _random_date_in_month(rng, year, month)

                # End current subscription
                for s in subscriptions:
                    if s["id"] == info["sub_id"]:
                        s["ended_at"] = datetime.combine(change_date, datetime.min.time())
                        s["status"] = change_type + "d"  # 'upgraded' or 'downgraded'
                        break

                # Create new subscription
                sub_id += 1
                subscriptions.append(
                    {
                        "id": sub_id,
                        "customer_id": cid,
                        "plan": new_plan,
                        "mrr": new_mrr,
                        "seats": new_seats,
                        "billing_cycle": info["billing_cycle"],
                        "started_at": datetime.combine(change_date, datetime.min.time()),
                        "ended_at": None,
                        "status": "active",
                        "cancellation_reason": None,
                    }
                )

                plan_changes.append(
                    {
                        "customer_id": cid,
                        "previous_plan": info["plan"],
                        "new_plan": new_plan,
                        "previous_mrr": info["mrr"],
                        "new_mrr": new_mrr,
                        "change_type": change_type,
                        "changed_at": datetime.combine(change_date, datetime.min.time()),
                    }
                )

                # Update active sub tracking
                active_subs[cid] = {
                    "sub_id": sub_id,
                    "plan": new_plan,
                    "mrr": new_mrr,
                    "seats": new_seats,
                    "billing_cycle": info["billing_cycle"],
                    "signup": info["signup"],
                }

        # Remove churned customers from active tracking
        for cid in churned_this_month:
            del active_subs[cid]

    # Add auto-increment IDs to tables that need them
    for i, pc in enumerate(plan_changes, 1):
        pc["id"] = i
    for i, um in enumerate(usage_metrics, 1):
        um["id"] = i

    return {
        "customers": pd.DataFrame(customers),
        "subscriptions": pd.DataFrame(subscriptions),
        "plan_changes": pd.DataFrame(plan_changes),
        "invoices": pd.DataFrame(invoices),
        "usage_metrics": pd.DataFrame(usage_metrics),
        "support_tickets": pd.DataFrame(support_tickets),
    }


# ---------------------------------------------------------------------------
# Load into database
# ---------------------------------------------------------------------------
def load_data(seed: int = 42, drop: bool = False) -> None:
    """Generate and load SaaS metrics data into PostgreSQL.

    Data is written to the ``public`` schema so it stays separate from
    Agno framework tables (``ai`` schema) and agent-managed data (``dash`` schema).
    """
    engine = create_engine(
        db_url,
        connect_args={"options": "-c search_path=public"},
    )

    if drop:
        print("Dropping existing tables...")
        with engine.connect() as conn:
            for table in ["usage_metrics", "support_tickets", "invoices", "plan_changes", "subscriptions", "customers"]:
                conn.execute(text(f'DROP TABLE IF EXISTS public."{table}" CASCADE'))
            conn.commit()

    print(f"Generating data (seed={seed})...\n")
    tables = generate(seed=seed)

    mode = "replace" if drop else "fail"
    total = 0
    for name, df in tables.items():
        print(f"  {name}: {len(df):,} rows", end=" ", flush=True)
        try:
            df.to_sql(name, engine, if_exists=mode, index=False)
        except ValueError:
            print(f"\n\nError: Table '{name}' already exists. Use --drop to replace existing data.")
            return
        print("OK")
        total += len(df)

    print(f"\nDone! {total:,} total rows")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate SaaS metrics sample data")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    parser.add_argument("--drop", action="store_true", help="Drop existing tables first")
    args = parser.parse_args()
    load_data(seed=args.seed, drop=args.drop)
