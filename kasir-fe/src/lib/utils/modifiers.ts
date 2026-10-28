import type { AddonGroup, OptionGroup } from '$lib/api/types';

type ModifierItem = {
  option_groups?: OptionGroup[];
  addon_groups?: AddonGroup[];
};

export function hasItemModifiers(item: ModifierItem) {
  return Boolean(
    item.option_groups?.some((group) => getGroupChoices(group).length > 0) ||
      item.addon_groups?.some((group) => getGroupChoices(group).length > 0)
  );
}

export function getAddonPriceTotal(item: ModifierItem, addonChoiceIds: string[]) {
  return (item.addon_groups ?? []).reduce((sum, group) => {
    return sum + getGroupChoices(group).reduce((groupSum, choice) => {
      return groupSum + (addonChoiceIds.includes(choice.id) ? getChoicePrice(choice) : 0);
    }, 0);
  }, 0);
}

type ModifierGroup = OptionGroup | AddonGroup;
type ModifierChoice = ReturnType<typeof getGroupChoices>[number];

export function getGroupChoices(group: ModifierGroup) {
  return group.choices ?? ('option_choices' in group ? group.option_choices : undefined) ?? ('addon_choices' in group ? group.addon_choices : undefined) ?? [];
}

export function getGroupLabel(group: ModifierGroup) {
  return group.name ?? group.label ?? 'Options';
}

export function getChoiceLabel(choice: ModifierChoice) {
  return choice.name ?? choice.label ?? 'Choice';
}

export function getChoicePrice(choice: ModifierChoice) {
  const value = 'extra_price' in choice ? choice.extra_price : 'price' in choice ? choice.price : 0;
  return typeof value === 'number' && Number.isFinite(value) ? value : 0;
}
