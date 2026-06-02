import { redirect } from "next/navigation";

export default function LegacyDataBrowserPage() {
  redirect("/raw-data");
}
