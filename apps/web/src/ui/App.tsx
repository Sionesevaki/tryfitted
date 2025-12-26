import { useState } from "react";
import { FitLab } from "./FitLab";
import { AvatarLab } from "./AvatarLab";

export function App() {
  const [activeTab, setActiveTab] = useState<"fit" | "avatar">("fit");

  return (
    <div className="app">
      <nav className="nav">
        <h1>TryFitted Labs</h1>
        <div className="tabs">
          <button
            className={activeTab === "fit" ? "active" : ""}
            onClick={() => setActiveTab("fit")}
          >
            Fit Lab
          </button>
          <button
            className={activeTab === "avatar" ? "active" : ""}
            onClick={() => setActiveTab("avatar")}
          >
            Avatar Lab
          </button>
        </div>
      </nav>
      <main>
        {activeTab === "fit" ? <FitLab /> : <AvatarLab />}
      </main>
    </div>
  );
}
