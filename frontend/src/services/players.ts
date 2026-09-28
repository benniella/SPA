import { api, type RequestOptions } from "@/lib/api-client";
import { queryString } from "@/services/query";
import type { Page, Player, PlayerCreate } from "@/types/api";

export interface ListPlayersParams {
  limit?: number;
  offset?: number;
  teamId?: string;
  onDate?: string;
}

export function listPlayers(
  organizationId: string,
  params: ListPlayersParams = {},
  options?: RequestOptions,
): Promise<Page<Player>> {
  return api.get<Page<Player>>(
    `/players${queryString({
      organization_id: organizationId,
      limit: params.limit,
      offset: params.offset,
      team_id: params.teamId,
      on_date: params.onDate,
    })}`,
    options,
  );
}

export function getPlayer(
  id: string,
  organizationId: string,
  options?: RequestOptions,
): Promise<Player> {
  return api.get<Player>(
    `/players/${encodeURIComponent(id)}${queryString({ organization_id: organizationId })}`,
    options,
  );
}

export function createPlayer(payload: PlayerCreate, options?: RequestOptions): Promise<Player> {
  return api.post<Player>("/players", payload, options);
}
