from google_auth_oauthlib.flow import InstalledAppFlow
import json

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def get_oauth_credentials():
    flow = InstalledAppFlow.from_client_secrets_file(
        'client_secret_318862727100-k4jt33f7h6uvbm5fh9a9ll76ro23v8b3.apps.googleusercontent.com.json', SCOPES)
    creds = flow.run_local_server(port=0)
    
    # Print the credentials in the format needed for secrets.toml
    credentials_dict = {
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
    }
    
    print("\nAdd this to your .streamlit/secrets.toml:")
    print("\n[google_credentials]")
    for key, value in credentials_dict.items():
        print(f'{key} = "{value}"')

if __name__ == '__main__':
    get_oauth_credentials()