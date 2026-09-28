<script setup lang="ts">
import { useAppStore } from '../../../store/app-store'

// 页面直接使用共享状态与操作，切换标签时不会丢失正在填写的草稿。
const {
  version,
  busy,
  materials,
  boms,
  bomForm,
  can,
  localTime,
  createBom,
  activateBom,
  retireBom,
  cancelBom
} = useAppStore()
</script>

<template>
  <section class="stack">
    <div v-if="can('bom.create')" class="card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">BILL OF MATERIALS</p>
          <h2>新建 BOM 版本</h2>
        </div>
        <span class="pill">草稿</span>
      </div>
      <p class="muted">
        BOM
        记录生产指定数量成品所需的组件。旧版本会保留供追溯；同一成品一次只能启用一个版本。
      </p>
      <form @submit.prevent="createBom">
        <div class="form-grid">
          <label
            >成品物料<select
              v-model.number="bomForm.product_material_id"
              required
            >
              <option :value="0" disabled>选择成品</option>
              <option v-for="item in materials" :key="item.id" :value="item.id">
                {{ item.sku }} · {{ item.name }}
              </option>
            </select></label
          ><label
            >基准产出数量<input
              v-model.trim="bomForm.base_quantity"
              type="number"
              min="0.001"
              max="1000000"
              step="0.001"
              required /></label
          ><label
            >版本说明（可选）<input v-model.trim="bomForm.note" maxlength="200"
          /></label>
        </div>
        <h3>组件用量</h3>
        <div
          v-for="(line, index) in bomForm.lines"
          :key="index"
          class="line-row"
        >
          <label
            >组件物料<select
              v-model.number="line.component_material_id"
              required
            >
              <option :value="0" disabled>选择组件</option>
              <option
                v-for="item in materials.filter(
                  (entry) => entry.id !== bomForm.product_material_id
                )"
                :key="item.id"
                :value="item.id"
              >
                {{ item.sku }} · {{ item.name }}
              </option>
            </select></label
          ><label
            >基准用量<input
              v-model.trim="line.quantity"
              type="number"
              min="0.001"
              max="1000000"
              step="0.001"
              required /></label
          ><button
            class="text-button"
            type="button"
            :disabled="bomForm.lines.length === 1"
            @click="bomForm.lines.splice(index, 1)"
          >
            移除
          </button>
        </div>
        <div class="form-actions">
          <button
            class="secondary"
            type="button"
            @click="
              bomForm.lines.push({ component_material_id: 0, quantity: '1' })
            "
          >
            添加组件</button
          ><button
            class="primary"
            type="submit"
            :disabled="busy || materials.length < 2"
          >
            保存草稿
          </button>
        </div>
      </form>
    </div>
    <div class="card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">BOM HISTORY</p>
          <h2>成品配方版本</h2>
        </div>
      </div>
      <div v-if="!boms.length" class="muted">暂无 BOM。</div>
      <article v-for="item in boms" :key="item.id" class="receipt">
        <div class="receipt-head">
          <div>
            <strong
              >#{{ item.id }} · {{ item.product_name }}（{{
                item.product_sku
              }}）· V{{ item.version }}</strong
            >
            <p class="muted">
              {{ localTime(item.created_at) }} · 创建人
              {{ item.created_by_name }} · 基准产出 {{ item.base_quantity }}
              {{ item.product_unit }}
              <span v-if="item.note">· {{ item.note }}</span>
            </p>
          </div>
          <div class="receipt-actions">
            <span class="pill" :class="item.status">{{
              {
                draft: '草稿',
                active: '已启用',
                retired: '已停用',
                cancelled: '已取消'
              }[item.status]
            }}</span
            ><button
              v-if="item.status === 'draft' && can('bom.activate')"
              class="primary small"
              type="button"
              :disabled="
                busy ||
                boms.some(
                  (other) =>
                    other.product_material_id === item.product_material_id &&
                    other.status === 'active'
                )
              "
              @click="activateBom(item.id)"
            >
              启用</button
            ><button
              v-if="item.status === 'active' && can('bom.retire')"
              class="secondary small"
              type="button"
              :disabled="busy"
              @click="retireBom(item.id)"
            >
              停用</button
            ><button
              v-if="item.status === 'draft' && can('bom.cancel')"
              class="secondary small"
              type="button"
              :disabled="busy"
              @click="cancelBom(item.id)"
            >
              取消草稿
            </button>
          </div>
        </div>
        <div class="receipt-lines">
          <span v-for="line in item.lines" :key="line.id"
            >{{ line.material_name }} × {{ line.quantity }}
            {{ line.unit }}</span
          >
        </div>
      </article>
    </div>
  </section>
</template>
