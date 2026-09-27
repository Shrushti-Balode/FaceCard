import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useAuth } from "@/hooks/useAuth";
import { CreditCard, Scan, Shield, Zap } from "lucide-react";
import heroImage from "@/assets/hero-bus.jpg";

const Landing = () => {
  const { user } = useAuth();

  return (
    <div className="min-h-screen bg-background">
      {/* Hero Section */}
      <section className="relative overflow-hidden bg-gradient-to-br from-primary/10 via-background to-secondary/10">
        <div className="absolute inset-0 bg-gradient-to-r from-primary/20 to-secondary/20"></div>
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
            <div className="text-center lg:text-left">
              <h1 className="text-4xl md:text-6xl font-bold text-foreground mb-6">
                <span className="bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">
                  FaceCard
                </span>
                <br />
                Smart Digital Bus Pass
              </h1>
              <p className="text-xl text-muted-foreground mb-8 max-w-lg">
                Experience the future of public transportation with face recognition technology, 
                digital payments, and real-time tracking.
              </p>
              <div className="flex flex-col sm:flex-row gap-4 justify-center lg:justify-start">
                {!user ? (
                  <Link to="/register">
                    <Button variant="hero" size="lg" className="w-full sm:w-auto">
                      Register Now
                    </Button>
                  </Link>
                ) : (
                  <Link to="/dashboard">
                    <Button variant="hero" size="lg" className="w-full sm:w-auto">
                      Go to Dashboard
                    </Button>
                  </Link>
                )}
                <Button variant="outline" size="lg" className="w-full sm:w-auto">
                  Learn More
                </Button>
              </div>
            </div>
            <div className="relative">
              <img 
                src={heroImage} 
                alt="Smart Bus System" 
                className="rounded-2xl shadow-strong w-full max-w-lg mx-auto"
              />
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-24 bg-muted/30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-4">
              Why Choose FaceCard?
            </h2>
            <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
              Our smart digital bus pass system revolutionizes public transportation 
              with cutting-edge technology and seamless user experience.
            </p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
            <Card className="text-center border-0 shadow-medium hover:shadow-strong transition-all duration-300">
              <CardContent className="p-6">
                <div className="bg-primary/10 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Scan className="h-8 w-8 text-primary" />
                </div>
                <h3 className="text-xl font-semibold text-foreground mb-2">Face Recognition</h3>
                <p className="text-muted-foreground">
                  Quick and secure boarding with advanced facial recognition technology.
                </p>
              </CardContent>
            </Card>

            <Card className="text-center border-0 shadow-medium hover:shadow-strong transition-all duration-300">
              <CardContent className="p-6">
                <div className="bg-secondary/10 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4">
                  <CreditCard className="h-8 w-8 text-secondary" />
                </div>
                <h3 className="text-xl font-semibold text-foreground mb-2">Digital Wallet</h3>
                <p className="text-muted-foreground">
                  Seamless payments with our integrated digital wallet system.
                </p>
              </CardContent>
            </Card>

            <Card className="text-center border-0 shadow-medium hover:shadow-strong transition-all duration-300">
              <CardContent className="p-6">
                <div className="bg-accent/10 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Zap className="h-8 w-8 text-accent" />
                </div>
                <h3 className="text-xl font-semibold text-foreground mb-2">Real-time Tracking</h3>
                <p className="text-muted-foreground">
                  Track your bus in real-time and plan your journey efficiently.
                </p>
              </CardContent>
            </Card>

            <Card className="text-center border-0 shadow-medium hover:shadow-strong transition-all duration-300">
              <CardContent className="p-6">
                <div className="bg-destructive/10 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Shield className="h-8 w-8 text-destructive" />
                </div>
                <h3 className="text-xl font-semibold text-foreground mb-2">Secure & Safe</h3>
                <p className="text-muted-foreground">
                  Bank-grade security ensures your data and payments are protected.
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-24 bg-gradient-to-r from-primary to-secondary">
        <div className="max-w-4xl mx-auto text-center px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
            Ready to Experience Smart Transit?
          </h2>
          <p className="text-xl text-white/90 mb-8">
            Join thousands of commuters who have already switched to FaceCard 
            for a faster, safer, and smarter travel experience.
          </p>
          {!user && (
            <Link to="/register">
              <Button 
                variant="secondary" 
                size="lg" 
                className="bg-white text-primary hover:bg-white/90"
              >
                Get Started Today
              </Button>
            </Link>
          )}
        </div>
      </section>
    </div>
  );
};

export default Landing;