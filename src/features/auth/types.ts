export type UserRole = "SUPER_ADMIN" | "NORMAL_USER";

export type CurrentUser = {
  username: string;
  role: UserRole;
};

export type LoginRequest = {
  username: string;
  password: string;
};

export type LogoutResponse = {
  success: boolean;
};
