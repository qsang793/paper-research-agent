export interface Citation {
    title: string;
    authors: string[];
    url: string;
    relevance_score: number;
    snippet?: string;
    arxiv_id?: string;
}

export interface FeaturesResponse {
    research_search_available: boolean;
}

export class ApiClient {
    static async getFeatures(): Promise<FeaturesResponse> {
        try {
            const response = await fetch("/api/features", { cache: "no-store" });
            if (!response.ok) {
                return { research_search_available: false };
            }
            return await response.json();
        } catch {
            // Fail closed if the backend feature endpoint is unavailable.
            return { research_search_available: false };
        }
    }
}
