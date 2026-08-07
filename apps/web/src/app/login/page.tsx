import { redirect } from "next/navigation";

// Login não é mais necessário — token configurado via .env.local
export default function LoginPage() {
  redirect("/dashboard");
}
