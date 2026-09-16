import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as authApi from '../../api/auth';
import type { UserProfile } from '../../types/jobcraft';

export const PROFILE_QUERY_KEY = ['profile'] as const;

/** authApi.getProfile()/updateProfile() 的扁平响应体（后端字段 snake_case）。 */
export interface ProfilePayload {
  display_name?: string;
  avatar_url?: string;
  role?: string;
  target_salary?: string;
  years_of_exp?: number;
  city?: string;
  email?: string;
  phone?: string;
  summary?: string;
  target_roles?: string[];
  target_companies?: string[];
  target_cities?: string[];
}

/** 空态默认值：与 JobCraftContext 初始 user 对齐，保证资料加载前的展示一致。 */
export const EMPTY_PROFILE: UserProfile = {
  name: '',
  avatarUrl: '',
  role: '求职者',
  targetSalary: '',
  yearsOfExp: 0,
  city: '',
};

/** 把领域字段更新映射为后端 snake_case patch（与 context updateUserProfile 同构）。 */
export function toApiProfilePatch(updates: Partial<UserProfile>): ProfilePayload {
  const patch: ProfilePayload = {};
  if (updates.name !== undefined) patch.display_name = updates.name;
  if (updates.avatarUrl !== undefined) patch.avatar_url = updates.avatarUrl;
  if (updates.role !== undefined) patch.role = updates.role;
  if (updates.targetSalary !== undefined) patch.target_salary = updates.targetSalary;
  if (updates.yearsOfExp !== undefined) patch.years_of_exp = updates.yearsOfExp;
  if (updates.city !== undefined) patch.city = updates.city;
  if (updates.email !== undefined) patch.email = updates.email;
  if (updates.phone !== undefined) patch.phone = updates.phone;
  if (updates.summary !== undefined) patch.summary = updates.summary;
  if (updates.targetRoles !== undefined) patch.target_roles = updates.targetRoles;
  if (updates.targetCompanies !== undefined) patch.target_companies = updates.targetCompanies;
  if (updates.targetCities !== undefined) patch.target_cities = updates.targetCities;
  return patch;
}

/** 合并 auth 用户信息与已落库资料（getProfile 失败时降级用 auth 侧字段）。 */
async function fetchUserProfile(): Promise<UserProfile> {
  const [authUser, rawProfile] = await Promise.all([
    authApi.getCurrentUser(),
    authApi.getProfile().catch(() => ({})),
  ]);
  const pd = rawProfile as Record<string, unknown>;
  return {
    name: (pd.display_name as string) || authUser.display_name || authUser.username,
    avatarUrl: (pd.avatar_url as string) || '',
    role: (pd.role as string) || '求职者',
    targetSalary: (pd.target_salary as string) || '',
    yearsOfExp: (pd.years_of_exp as number) || 0,
    city: (pd.city as string) || '',
    email: (pd.email as string) || authUser.email || '',
    phone: (pd.phone as string) || '',
    summary: (pd.summary as string) || '',
    targetRoles: (pd.target_roles as string[]) || [],
    targetCompanies: (pd.target_companies as string[]) || [],
    targetCities: (pd.target_cities as string[]) || [],
  };
}

/** 当前用户资料查询。数据缓存在 react-query，单一真相源。 */
export function useProfileQuery() {
  return useQuery({ queryKey: PROFILE_QUERY_KEY, queryFn: fetchUserProfile });
}

/** 部分更新用户资料；成功后同步 react-query 缓存（乐观合并，不整页 refetch）。 */
export function useUpdateProfileMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (updates: Partial<UserProfile>) => {
      await authApi.updateProfile(toApiProfilePatch(updates) as unknown as Record<string, unknown>);
      return updates;
    },
    onSuccess: (updates) => {
      queryClient.setQueryData<UserProfile>(PROFILE_QUERY_KEY, (prev) => ({
        ...EMPTY_PROFILE,
        ...(prev ?? {}),
        ...updates,
      }));
    },
  });
}