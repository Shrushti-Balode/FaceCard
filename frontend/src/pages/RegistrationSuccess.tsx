import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/hooks/useAuth";
import { CheckCircle, MapPin, Wallet, ArrowRight } from "lucide-react";

const RegistrationSuccess = () => {
  const { user } = useAuth();

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-muted/30">
        <Card>
          <CardContent className="p-8 text-center">
            <p className="text-muted-foreground">No registration data found.</p>
            <Link to="/register">
              <Button className="mt-4">Go to Registration</Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-muted/30 py-12">
      <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8">
        <Card className="shadow-strong">
          <CardHeader className="text-center">
            <div className="flex justify-center mb-4">
              <div className="bg-secondary/20 p-4 rounded-full">
                <CheckCircle className="h-16 w-16 text-secondary" />
              </div>
            </div>
            <CardTitle className="text-3xl font-bold text-foreground">
              Registration Successful!
            </CardTitle>
            <p className="text-lg text-muted-foreground mt-2">
              Welcome to FaceCard, {user.firstName}!
            </p>
          </CardHeader>
          
          <CardContent className="space-y-6">
            {/* Registration Details */}
            <div className="bg-muted/50 rounded-lg p-6 space-y-4">
              <h3 className="text-lg font-semibold text-foreground flex items-center gap-2">
                <MapPin className="h-5 w-5 text-primary" />
                Your Route Details
              </h3>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-muted-foreground">Route</p>
                  <p className="font-medium text-foreground">{user.route}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Pickup Stop</p>
                  <p className="font-medium text-foreground">{user.pickup}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Drop Stop</p>
                  <p className="font-medium text-foreground">{user.drop}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Face Card ID</p>
                  <p className="font-medium text-foreground">{user.id}</p>
                </div>
              </div>
            </div>

            {/* Wallet Information */}
            <div className="bg-secondary/10 rounded-lg p-6">
              <h3 className="text-lg font-semibold text-foreground flex items-center gap-2 mb-3">
                <Wallet className="h-5 w-5 text-secondary" />
                Wallet Balance
              </h3>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-2xl font-bold text-secondary">₹{user.wallet}</p>
                  <p className="text-sm text-muted-foreground">Available Balance</p>
                </div>
                <div className="text-right">
                  <p className="text-sm text-muted-foreground">Status</p>
                  <p className="font-medium text-secondary">Active</p>
                </div>
              </div>
            </div>

            {/* Important Information */}
            <div className="bg-accent/10 border border-accent/20 rounded-lg p-6">
              <h3 className="font-semibold text-foreground mb-3">Important Information</h3>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li className="flex items-start gap-2">
                  <span className="text-accent">•</span>
                  Your face image was registered and linked to your Face Card ID.
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-accent">•</span>
                  At least ₹5 is required to start a journey.
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-accent">•</span>
                  Fare is calculated as ₹5 per stop traveled.
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-accent">•</span>
                  Your digital pass is now active and ready to use.
                </li>
              </ul>
            </div>

            {/* Action Buttons */}
            <div className="flex flex-col sm:flex-row gap-4">
              <Link to="/dashboard" className="flex-1">
                <Button variant="hero" size="lg" className="w-full">
                  <ArrowRight className="h-4 w-4 mr-2" />
                  Go to Dashboard
                </Button>
              </Link>
              <Link to="/wallet" className="flex-1">
                <Button variant="outline" size="lg" className="w-full">
                  <Wallet className="h-4 w-4 mr-2" />
                  Manage Wallet
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default RegistrationSuccess;