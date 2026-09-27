import { Link, useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import { CreditCard, Home, User, Wallet, LogOut } from "lucide-react";

const Navbar = () => {
  const location = useLocation();
  const { user, logout } = useAuth();

  const isActive = (path: string) => location.pathname === path;

  return (
    <nav className="bg-card border-b border-border shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          <div className="flex items-center">
            <Link to="/" className="flex items-center space-x-2">
              <CreditCard className="h-8 w-8 text-primary" />
              <span className="text-xl font-bold text-primary">FaceCard</span>
            </Link>
          </div>

          <div className="hidden md:block">
            <div className="ml-10 flex items-baseline space-x-4">
              <Link to="/">
                <Button
                  variant={isActive("/") ? "default" : "ghost"}
                  className="flex items-center space-x-1"
                >
                  <Home className="h-4 w-4" />
                  <span>Home</span>
                </Button>
              </Link>

              {!user ? (
                <Link to="/register">
                  <Button
                    variant={isActive("/register") ? "default" : "ghost"}
                    className="flex items-center space-x-1"
                  >
                    <User className="h-4 w-4" />
                    <span>Register</span>
                  </Button>
                </Link>
              ) : (
                <>
                  <Link to="/dashboard">
                    <Button
                      variant={isActive("/dashboard") ? "default" : "ghost"}
                      className="flex items-center space-x-1"
                    >
                      <User className="h-4 w-4" />
                      <span>Dashboard</span>
                    </Button>
                  </Link>
                  <Link to="/wallet">
                    <Button
                      variant={isActive("/wallet") ? "default" : "ghost"}
                      className="flex items-center space-x-1"
                    >
                      <Wallet className="h-4 w-4" />
                      <span>Wallet</span>
                    </Button>
                  </Link>
                  <Link to="/admin/gate">
                    <Button
                      variant={isActive("/admin/gate") ? "default" : "ghost"}
                      className="flex items-center space-x-1"
                    >
                      <User className="h-4 w-4" />
                      <span>Live Gate</span>
                    </Button>
                  </Link>
                  <Button
                    variant="ghost"
                    onClick={logout}
                    className="flex items-center space-x-1 text-destructive hover:text-destructive"
                  >
                    <LogOut className="h-4 w-4" />
                    <span>Logout</span>
                  </Button>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;