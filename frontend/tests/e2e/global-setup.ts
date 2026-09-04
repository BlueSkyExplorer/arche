const healthURL = "http://localhost:8000/api/v1/health";

export default async function globalSetup() {
  try {
    const response = await fetch(healthURL);
    if (response.ok) return;
    throw new Error(`status ${response.status}`);
  } catch (error) {
    throw new Error(
      `The E2E backend is not healthy at ${healthURL}. Start the stub-auth backend before running pnpm test:e2e.`,
      { cause: error },
    );
  }
}
