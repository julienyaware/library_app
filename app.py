from flask import Flask, render_template, request
import requests

app = Flask(__name__)

# Configuration for access to Folio
API_BASE_URL = "https://kong-gvsu-test.folio.ebsco.com"
X_OKAPI_TENANT_VALUE = "fs00001041"
USERNAME = "chkoutreporttest"
PASSWORD = "@chKoutreport133"

# Create session and login using credentials
def create_session():
    """Logs into the FOLIO system using configured
    credentials and returns a requests.Session with authentication tokens applied."""
    session = requests.Session()

    #Tenant header for all Folio requests
    session.headers.update({"x-okapi-tenant": X_OKAPI_TENANT_VALUE})

    login_url = f"{API_BASE_URL}/authn/login-with-expiry"
    payload = {"username": USERNAME, "password": PASSWORD}

    resp = session.post(login_url, json=payload)
    resp.raise_for_status()

    # Extract the token from the cookie
    token = None
    for cookie in resp.cookies:
        if "token" in cookie.name.lower():
            token = cookie.value
            break

    if not token:
        raise Exception("Authentication failed: access token not found in cookies")

    # Attach token to all future requests
    session.headers.update({"x-okapi-token": token})

    return session

def search_instances(session, subject, limit=10, offset=0):
    """
    Search instances by a specific value.
    """
    url = f"{API_BASE_URL}/search/instances"
    params = {
        "expandAll": "true",
        "query": f'subjects=="{subject}"',
        "limit": limit,
        "offset": offset
    }

    resp = session.get(url, params=params)
    resp.raise_for_status()
    return resp.json()

def get_all_instances(session, limit=10, offset=0):
    """
    Retrieve all instance records at once.
    """
    url = f"{API_BASE_URL}/inventory/instances"
    params = {"limit": limit, "offset": offset}

    resp = session.get(url, params=params)
    resp.raise_for_status()
    return resp.json()


# Home page route
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/results", methods=["GET"])
def results():
    subject = request.args.get("subject", "").strip()
    if not subject:
        return render_template("results.html",
                               records=[],
                               subject="",
                               page=1,
                               total_records=0,
                               limit=10)

    page = int(request.args.get("page", 1))
    limit = 10
    offset = (page - 1) * limit

    try:
        # Get a logged-in session
        session = create_session()

        # Search for instances
        data = search_instances(session, subject, limit=limit, offset=offset)
    except Exception as e:
        # Handle errors  for the user
        return render_template("results.html",
                               records=[],
                               subject=subject,
                               page=1,
                               total_records=0,
                               limit=10,
                               error=str(e))

    total_records = data.get("totalRecords", 0)
    instances = data.get("instances", [])

    records = []
    for r in instances:
        record = {
            "title": r.get("title", "No Title"),
            "subjects": r.get("subjects", []),
            "contributors": [c.get("name") for c in r.get("contributors", [])] if r.get("contributors") else [],
            "createdDate": r.get("metadata", {}).get("createdDate", "N/A")
        }
        records.append(record)

    return render_template(
        "results.html",
        records=records,
        subject=subject,
        page=page,
        total_records=total_records,
        limit=limit
    )


if __name__ == "__main__":
    app.run(debug=True, port=8000)