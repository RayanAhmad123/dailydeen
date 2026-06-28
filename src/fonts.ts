import { loadFont as loadCormorant } from "@remotion/google-fonts/CormorantGaramond";
import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import { loadFont as loadAmiri } from "@remotion/google-fonts/Amiri";

const cormorant = loadCormorant("normal", { weights: ["600", "700"] });
const inter = loadInter("normal", { weights: ["400", "500"] });
const amiri = loadAmiri("normal", { weights: ["400", "700"] });

export const serifFamily = cormorant.fontFamily;
export const sansFamily = inter.fontFamily;
export const arabicFamily = amiri.fontFamily; // Quran Arabic (Amiri)
