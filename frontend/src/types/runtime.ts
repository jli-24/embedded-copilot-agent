export interface ModelRuntimeStatus {
  provider: string;
  status: string;
  capabilities: string[];
  model: string | null;
}
