class AuthRefreshNow(Exception):
    "The app needs to be refreshed."
    def __init__(self):
        self.name = 'AuthRefreshNow'
        self.message = 'Token is refreshed.'
        super().__init__(self.message) # Return to message when str(exp)

class AuthTokenOffline(Exception):
    "User is offline."
    def __init__(self): 
        self.name = 'AuthTokenOffline'
        self.message = 'Offline'
        super().__init__(self.message) # Return to message when str(exp)

class AuthTokenLogout(Exception):
    "Need to logout."
    def __init__(self):
        self.name = 'AuthTokenLogout'
        self.message = 'Logout'
        super().__init__(self.message) # Return to message when str(exp)

class AuthAccessTokenExpired(Exception):
    "Try to renew an access token."
    def __init__(self):
        self.name = 'AuthAccessTokenExpired'
        self.message = 'Try to renew an access token.'
        super().__init__(self.message) # Return to message when str(exp)