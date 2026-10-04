import * as directionApi from '../../api/direction';
import * as jobApi from '../../api/job';

/**
 * 结构化表单方向分类状态与提交链（T-M4-3，Q4 裁决：手动 + 词典规则，零 LLM）。
 *
 * 提交时序（分析创建成功后执行，独立于分析成功与否）：
 * 1. 有方向名 → POST /direction/find-or-create 拿 direction_id（新建时以表单六维播种画像）；
 * 2. 六维 = 表单值优先，空字段回退所选方向自带画像（选已有方向即继承其画像）；
 * 3. 六维全空（含回退后）→ skipped + 提醒原因（方向可能已建，但不写分类行——
 *    后端 JdClassificationPayload「至少一维非空」校验，违者 422）；
 * 4. upsert POST /job/{id}/jd-classification，provenance 映射：
 *    词典建议未改动 → source=rule / confidence=low / status=proposed（低置信待确认）；
 *    手动填写或改过 → source=manual / confidence=high / status=confirmed（用户已确认）。
 */

export interface ClassificationValue {
  directionName: string;
  jobFunction: string;
  primaryRole: string;
  industry: string;
  product: string;
  scenario: string;
  skills: string;
}

/** 分类值来源：词典建议（rule）或手动（manual）；任何手动编辑都会把 rule 翻回 manual。 */
export type ClassificationSource = 'manual' | 'rule';

export const EMPTY_CLASSIFICATION: ClassificationValue = {
  directionName: '',
  jobFunction: '',
  primaryRole: '',
  industry: '',
  product: '',
  scenario: '',
  skills: '',
};

/** 后端六维字段名（wire）→ 表单字段名（view）。 */
const FORM_DIM_BY_WIRE = {
  job_function: 'jobFunction',
  primary_role: 'primaryRole',
  industry: 'industry',
  product: 'product',
  scenario: 'scenario',
  skills: 'skills',
} as const;

type WireDimKey = keyof typeof FORM_DIM_BY_WIRE;

const WIRE_DIM_FIELDS = Object.keys(FORM_DIM_BY_WIRE) as WireDimKey[];

/** 表单是否含分类输入（方向名或任一维度非空）——全空则提交链整体跳过。 */
export function hasClassificationInput(value: ClassificationValue): boolean {
  if (value.directionName.trim()) return true;
  return WIRE_DIM_FIELDS.some((wireKey) => value[FORM_DIM_BY_WIRE[wireKey]].trim());
}

export interface SubmitClassificationResult {
  status: 'saved' | 'skipped';
  /** skipped 且需要用户提醒时的原因（静默跳过 = 无输入，不提醒）。 */
  reason?: string;
}

/**
 * 提交方向分类（分析已创建、拿到 job_analysis_id 后调用）。
 *
 * @param jobAnalysisId 后端分析 id（数字）
 * @param value 表单分类值
 * @param source 分类值来源（决定 confidence/status 映射）
 * @returns saved = 分类已落库；skipped = 无输入（reason 空）或无维度可写（reason 非空待提醒）
 * @throws find-or-create / upsert 失败原样上抛（调用方 error toast）
 */
export async function submitClassification(
  jobAnalysisId: number,
  value: ClassificationValue,
  source: ClassificationSource,
): Promise<SubmitClassificationResult> {
  if (!hasClassificationInput(value)) return { status: 'skipped' };

  let directionId: number | null = null;
  let fallback: directionApi.DirectionRead | null = null;

  const name = value.directionName.trim();
  if (name) {
    const payload: { name: string } & Partial<Record<WireDimKey, string>> = { name };
    for (const wireKey of WIRE_DIM_FIELDS) {
      const v = value[FORM_DIM_BY_WIRE[wireKey]].trim();
      if (v) payload[wireKey] = v;
    }
    const result = await directionApi.findDirectionOrCreate(payload);
    directionId = result.direction.id;
    fallback = result.direction;
  }

  const dims = {} as Record<WireDimKey, string>;
  for (const wireKey of WIRE_DIM_FIELDS) {
    dims[wireKey] = value[FORM_DIM_BY_WIRE[wireKey]].trim() || fallback?.[wireKey] || '';
  }

  if (!WIRE_DIM_FIELDS.some((wireKey) => dims[wireKey])) {
    return {
      status: 'skipped',
      reason: '方向分类未保存：请至少填写一个分类维度（或选择已带画像的方向）',
    };
  }

  await jobApi.upsertJdClassification(jobAnalysisId, {
    direction_id: directionId,
    ...dims,
    confidence: source === 'rule' ? 'low' : 'high',
    source,
    status: source === 'rule' ? 'proposed' : 'confirmed',
  });

  return { status: 'saved' };
}
