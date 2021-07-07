# security functions

def authorize(user, C):
	if user.id in C["sudoers"]:	return True
	if user.id in C["authorized"]: return True
	for role in user.roles:
		if role.id in C["authorized"] or role.id in C["sudoers"]:
			return True
	return False

def authorize_sudoer(user, C):
	if user.id in C["sudoers"]:	return True
	for role in user.roles:
		if role.id in C["sudoers"]:
			return True