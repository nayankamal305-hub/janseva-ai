"""Collect grievance-officer / escalation emails that companies publish on their OWN pages. Keeps an email only if it appears within 400 chars of
'grievance' or 'nodal' or 'escalat' and its domain belongs to the company. Source URL + date stored. Re-runnable."""
import json, re, ssl, sys, urllib.request
CTX = ssl.create_default_context()
C = [("Swiggy", "food_delivery", "swiggy.com", ["https://www.swiggy.com/privacy-policy", "https://www.swiggy.com/corporate/contact-us/", "https://www.swiggy.com/terms-and-conditions"]),
 ("Zomato", "food_delivery", "zomato.com", ["https://www.zomato.com/contact", "https://www.zomato.com/policies/"]),
 ("Uber India", "ride_hailing", "uber.com", ["https://help.uber.com/en/riders/article/grievance-redressal?nodeId=c04af4d0-930c-4098-b099-5f6f2a2fff84"]),
 ("Ola", "ride_hailing", "olacabs.com", ["https://www.olacabs.com/contact"]),
 ("Amazon India", "ecommerce", "amazon.in", ["https://www.amazon.in/gp/help/customer/display.html?nodeId=GX7NJQ4ZB8MHFRNJ"]),
 ("Flipkart", "ecommerce", "flipkart.com", ["https://stories.flipkart.com/terms-of-use", "https://stories.flipkart.com/privacy-policy"]),
 ("Myntra", "ecommerce", "myntra.com", ["https://www.myntra.com/grievanceredressal"]),
 ("Paytm", "payments", "paytm.com", ["https://paytm.com/company/grievance"]),
 ("PhonePe", "payments", "phonepe.com", ["https://www.phonepe.com/grievance-policy/", "https://www.phonepe.com/contact-us/"]),
 ("MakeMyTrip", "travel", "makemytrip.com", ["https://www.makemytrip.com/legal/in/eng/user-agreement.html"]),
 ("IRCTC", "railway_ticketing", "irctc.co.in", ["https://contents.irctc.co.in/en/ContactUsEn.html"]),
 ("BigBasket", "grocery", "bigbasket.com", ["https://www.bigbasket.com/faq/"])]
EM = re.compile(r"[A-Za-z0-9._%+\-]+(?:\s?\[at\]\s?|@)[A-Za-z0-9\-]+(?:\s?\[dot\]\s?|\.)[A-Za-z0-9.\-]*[A-Za-z]", re.I)
def get(u):
    try: return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=15, context=CTX).read(1500000).decode("utf-8", "ignore")
    except Exception as e: return None
out = []
for name, cat, dom, urls in C:
    found = {}; ok = []
    for u in urls:
        h = get(u)
        if not h: continue
        ok.append(u); t = re.sub(r"\s+", " ", re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", h, flags=re.S))
        for m in EM.finditer(t):
            e = re.sub(r"\s", "", m.group(0).replace("[at]", "@").replace("[dot]", ".")).lower().strip(".")
            if not re.match(r"^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$", e) or not e.split("@")[1].endswith(dom.split(".")[0] + "." + dom.split(".", 1)[1]) and dom.split(".")[0] not in e.split("@")[1]: continue
            ctx = t[max(0, m.start() - 400): m.end() + 200].lower()
            if re.search(r"grievance|nodal|escalat|redress", ctx): found.setdefault(e, u)
    out.append({"company": name, "sector": cat, "domain": dom, "grievance_emails": [{"email": e, "found_on": u} for e, u in found.items()][:4], "pages_read": ok, "accepts_complaints": "published by company as grievance contact" if found else "none found", "last_verified": "2026-11-27"})
json.dump(out, open("data/companies.json", "w"), indent=1, ensure_ascii=False)
for o in out: print(o["company"], [x["email"] for x in o["grievance_emails"]], len(o["pages_read"]))
