<script setup lang="ts">
import { useAppStore } from '../../../store/app-store'

// 页面直接使用共享状态与操作，切换标签时不会丢失正在填写的草稿。
const {
  busy,
  materials,
  suppliers,
  warehouses,
  materialForm,
  supplierForm,
  warehouseForm,
  can,
  createMaterial,
  createSupplier,
  createWarehouse
} = useAppStore()
</script>

<template>
  <section class="stack">
    <div class="two-columns">
      <div class="card">
        <div class="section-heading">
          <div>
            <p class="eyebrow">MATERIALS</p>
            <h2>物料</h2>
          </div>
        </div>
        <form
          v-if="can('catalog.manage')"
          class="inline-form"
          @submit.prevent="createMaterial"
        >
          <label
            >物料编码<input
              v-model.trim="materialForm.sku"
              required
              maxlength="40"
              placeholder="SKU-001" /></label
          ><label
            >名称<input
              v-model.trim="materialForm.name"
              required
              maxlength="120"
              placeholder="物料名称" /></label
          ><label
            >单位<input
              v-model.trim="materialForm.unit"
              required
              maxlength="20"
              placeholder="件" /></label
          ><button class="primary" type="submit" :disabled="busy">
            添加物料
          </button>
        </form>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>编码</th>
                <th>名称</th>
                <th>单位</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in materials" :key="item.id">
                <td class="mono">{{ item.sku }}</td>
                <td>{{ item.name }}</td>
                <td>{{ item.unit }}</td>
              </tr>
              <tr v-if="!materials.length">
                <td colspan="3" class="muted">暂无物料。</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <div class="card">
        <div class="section-heading">
          <div>
            <p class="eyebrow">SUPPLIERS</p>
            <h2>供应商</h2>
          </div>
        </div>
        <form
          v-if="can('catalog.manage')"
          class="inline-form"
          @submit.prevent="createSupplier"
        >
          <label
            >供应商名称<input
              v-model.trim="supplierForm.name"
              required
              maxlength="120"
              placeholder="输入供应商名称" /></label
          ><button class="primary" type="submit" :disabled="busy">
            添加供应商
          </button>
        </form>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>名称</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in suppliers" :key="item.id">
                <td>{{ item.name }}</td>
              </tr>
              <tr v-if="!suppliers.length">
                <td class="muted">暂无供应商。</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
    <div class="card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">WAREHOUSES</p>
          <h2>仓库</h2>
        </div>
      </div>
      <form
        v-if="can('warehouse.manage')"
        class="inline-form"
        @submit.prevent="createWarehouse"
      >
        <label
          >仓库编码<input
            v-model.trim="warehouseForm.code"
            required
            maxlength="40"
            pattern="[A-Za-z0-9_-]+"
            placeholder="例如 EAST" /></label
        ><label
          >仓库名称<input
            v-model.trim="warehouseForm.name"
            required
            maxlength="80"
            placeholder="例如东区仓库" /></label
        ><button class="primary" type="submit" :disabled="busy">
          添加仓库
        </button>
      </form>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>编码</th>
              <th>名称</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in warehouses" :key="item.id">
              <td class="mono">{{ item.code }}</td>
              <td>{{ item.name }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>
