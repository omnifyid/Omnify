export function toCategoryPayload(input: { name: string; icon?: string; sortOrder?: number }) {
  const icon = input.icon?.trim();
  return {
    name: input.name.trim(),
    ...(icon ? { icon } : {}),
    ...(input.sortOrder !== undefined ? { sort_order: input.sortOrder } : {})
  };
}

export type AddonGroupPayloadInput = {
  name: string;
  min_select?: number;
  max_select?: number | null;
  choices: Array<{
    name: string;
    extra_price: number;
  }>;
};

export type OptionGroupPayloadInput = {
  name: string;
  required?: boolean;
  choices: Array<{
    name: string;
    is_default?: boolean;
  }>;
};

export function toAddonGroupsPayload(groups: AddonGroupPayloadInput[]) {
  return groups
    .map((group, groupIndex) => ({
      name: group.name.trim(),
      min_select: group.min_select ?? 0,
      max_select: group.max_select ?? null,
      sort_order: groupIndex,
      choices: group.choices
        .filter((choice) => choice.name.trim())
        .map((choice, choiceIndex) => ({
          label: choice.name.trim(),
          extra_price: Math.max(0, Math.round(choice.extra_price || 0)),
          sort_order: choiceIndex
        }))
    }))
    .filter((group) => group.name && group.choices.length > 0);
}

export function toItemUpdatePayload(input: { name?: string; categoryId?: string; isAvailable?: boolean; basePrice?: number }) {
  return {
    ...(input.name !== undefined ? { name: input.name.trim() } : {}),
    ...(input.categoryId !== undefined ? { category_id: input.categoryId || null } : {}),
    ...(input.isAvailable !== undefined ? { is_available: input.isAvailable } : {}),
    ...(input.basePrice !== undefined ? { base_price: Math.max(0, Math.round(input.basePrice)) } : {})
  };
}

export function toOptionGroupsPayload(groups: OptionGroupPayloadInput[]) {
  return groups
    .map((group, groupIndex) => ({
      name: group.name.trim(),
      is_required: Boolean(group.required),
      sort_order: groupIndex,
      choices: group.choices
        .filter((choice) => choice.name.trim())
        .map((choice, choiceIndex) => ({ label: choice.name.trim(), is_default: Boolean(choice.is_default), sort_order: choiceIndex }))
    }))
    .filter((group) => group.name && group.choices.length > 0);
}
